#!/usr/bin/env bash
# Claude Code status line that also keeps claude-code-setup/status.json current.
#
# Claude Code pipes a JSON description of the session (model, version, context
# window) to this script on every status line refresh. The script prints a
# one-line status and, when a session starts or switches to a model or version
# the site has not published yet, commits a new status.json straight to the
# Pages branch in the background. The commit is built with git plumbing, so the
# working tree, the index, and the checked-out branch of the clone are never
# touched.
#
# Setup, in ~/.claude/settings.json:
#   "statusLine": { "type": "command", "command": "~/swchoi1994.github.io/claude-code-setup/sync-status.sh" }
#
# It also works as a SessionStart hook (prints nothing there), or piped from an
# existing status line script:  printf '%s' "$input" | .../sync-status.sh >/dev/null
#
# Optional environment:
#   CLAUDE_STATUS_REPO    clone to publish from (default: the clone holding this script)
#   CLAUDE_STATUS_REMOTE  remote name (default: origin)
#   CLAUDE_STATUS_BRANCH  branch GitHub Pages serves (default: main)
#
# State and the sync log live in <clone>/.git/claude-status/.

set -u

STATUS_PATH="claude-code-setup/status.json"
REMOTE="${CLAUDE_STATUS_REMOTE:-origin}"
BRANCH="${CLAUDE_STATUS_BRANCH:-main}"
RETRY_SECONDS=600

script_dir=$(cd "$(dirname "$0")" && pwd)
script_path="$script_dir/$(basename "$0")"
REPO="${CLAUDE_STATUS_REPO:-$script_dir/..}"

# Prints version, model id, display name, context size, hook event, and session
# id, one per line. Reads Claude Code's status line and hook JSON as well as
# our own status.json.
parse_json() {
    if command -v jq >/dev/null 2>&1; then
        jq -r '
            (.model | if type == "object" then . else {id: .} end) as $m
            | .version // .claude_code_version // "",
              $m.id // "",
              $m.display_name // "",
              (.context_window.context_window_size? // .context_window_size // "" | tostring),
              .hook_event_name // "",
              .session_id // ""
        ' 2>/dev/null
    elif command -v node >/dev/null 2>&1; then
        node -e '
            let raw = "";
            process.stdin.on("data", (d) => { raw += d; }).on("end", () => {
                let j = {};
                try { j = JSON.parse(raw) || {}; } catch (e) {}
                const m = j.model && typeof j.model === "object" ? j.model : { id: j.model };
                const out = [j.version || j.claude_code_version, m.id, m.display_name,
                    (j.context_window && j.context_window.context_window_size) || j.context_window_size,
                    j.hook_event_name, j.session_id];
                console.log(out.map((v) => (v == null ? "" : String(v))).join("\n"));
            });
        ' 2>/dev/null
    elif command -v python3 >/dev/null 2>&1; then
        python3 -c '
import json, sys
try:
    j = json.load(sys.stdin)
except Exception:
    j = {}
m = j.get("model")
m = m if isinstance(m, dict) else {"id": m}
cw = j.get("context_window") if isinstance(j.get("context_window"), dict) else {}
out = [j.get("version") or j.get("claude_code_version"), m.get("id"), m.get("display_name"),
       cw.get("context_window_size") or j.get("context_window_size"), j.get("hook_event_name"),
       j.get("session_id")]
print("\n".join("" if v is None else str(v) for v in out))
' 2>/dev/null
    else
        return 1
    fi
}

json_escape() {
    local s=${1//\\/\\\\}
    printf '%s' "${s//\"/\\\"}"
}

# "claude-opus-5-5" + 1M context -> "Opus 5.5 (1M context)". Mirrors modelName() in status.js.
pretty_model() {
    local id=$1 display=$2 ctx=$3 name="" family re='claude-([a-z]+)-([0-9]+)(-([0-9]{1,2}))?([^0-9]|$)'
    if [[ $id =~ $re ]]; then
        family=${BASH_REMATCH[1]}
        name="$(printf '%s' "${family:0:1}" | tr '[:lower:]' '[:upper:]')${family:1} ${BASH_REMATCH[2]}"
        [ -n "${BASH_REMATCH[4]}" ] && name="$name.${BASH_REMATCH[4]}"
    fi
    [ -z "$name" ] && name=${display:-${id:-Claude}}
    name=${name% (*context*)}
    if [ "${ctx:-0}" -ge 1000000 ] 2>/dev/null; then
        name="$name ($((ctx / 1000000))M context)"
    elif [[ $id == *"[1m]"* ]]; then
        name="$name (1M context)"
    fi
    printf '%s' "$name"
}

log() {
    printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"
}

mark_published() {
    printf '%s' "$1" > "$state_dir/published"
    printf '%s' "$1" > "$2"
    rm -f "$state_dir/attempt"
}

# Commits status.json to $REMOTE/$BRANCH without touching the working tree.
publish() {
    local version=$1 model_id=$2 display=$3 ctx=$4 source=$5 key=$6 session_file=$7
    local attempt base remote_key json blob index tree commit

    # Never wait for a password prompt in the background.
    export GIT_TERMINAL_PROMPT=0
    export GIT_SSH_COMMAND="${GIT_SSH_COMMAND:-ssh -o BatchMode=yes}"

    local waited=0
    until mkdir "$lock" 2>/dev/null; do
        # Another publish is running: wait for it, or clear a lock a crash left behind.
        if [ -n "$(find "$lock" -maxdepth 0 -mmin +5 2>/dev/null)" ]; then
            rm -rf "$lock"
        elif [ "$waited" -ge 30 ]; then
            log "another publish is still running; retrying later"
            return 1
        else
            sleep 1
            waited=$((waited + 1))
        fi
    done
    trap 'rm -rf "$lock"' EXIT
    trap 'exit 1' INT TERM
    find "$state_dir/sessions" -type f -mtime +7 -exec rm -f {} + 2>/dev/null

    for attempt in 1 2 3; do
        tree=""
        git -C "$REPO" fetch --quiet "$REMOTE" "+refs/heads/$BRANCH:refs/remotes/$REMOTE/$BRANCH" || { log "fetch failed"; return 1; }
        base=$(git -C "$REPO" rev-parse --verify --quiet "refs/remotes/$REMOTE/$BRANCH^{commit}") || { log "no $REMOTE/$BRANCH"; return 1; }

        if ! git -C "$REPO" cat-file -e "$base:$STATUS_PATH" 2>/dev/null; then
            log "$STATUS_PATH is not on $REMOTE/$BRANCH yet; merge the Claude Code setup page first"
            return 1
        fi

        remote_key=$(git -C "$REPO" show "$base:$STATUS_PATH" | parse_json | sed -n '1,4p' | tr '\n' '|')
        if [ "$remote_key" = "$key" ]; then
            mark_published "$key" "$session_file"
            log "already current: $key"
            return 0
        fi

        json=$(printf '{\n  "claude_code_version": "%s",\n  "model": {\n    "id": "%s",\n    "display_name": "%s"\n  },\n  "context_window_size": %s,\n  "updated_at": "%s",\n  "source": "%s"\n}' \
            "$(json_escape "$version")" "$(json_escape "$model_id")" "$(json_escape "$display")" \
            "${ctx:-null}" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$(json_escape "$source")")
        blob=$(printf '%s\n' "$json" | git -C "$REPO" hash-object -w --stdin) || { log "hash-object failed"; return 1; }

        index="$(mktemp -d)/index"
        GIT_INDEX_FILE=$index git -C "$REPO" read-tree "$base" &&
            GIT_INDEX_FILE=$index git -C "$REPO" update-index --add --cacheinfo "100644,$blob,$STATUS_PATH" &&
            tree=$(GIT_INDEX_FILE=$index git -C "$REPO" write-tree)
        rm -rf "$(dirname "$index")"
        [ -n "$tree" ] || { log "could not build tree"; return 1; }

        commit=$(git -C "$REPO" commit-tree "$tree" -p "$base" \
            -m "Update Claude Code status: $(pretty_model "$model_id" "$display" "$ctx"), v$version") || { log "commit failed"; return 1; }

        if git -C "$REPO" push --quiet "$REMOTE" "$commit:refs/heads/$BRANCH"; then
            git -C "$REPO" update-ref "refs/remotes/$REMOTE/$BRANCH" "$commit"
            mark_published "$key" "$session_file"
            log "published $key as ${commit:0:7}"
            return 0
        fi
        log "push attempt $attempt rejected; retrying"
        sleep "$attempt"
    done
    log "push failed after 3 attempts"
    return 1
}

if [ "${1:-}" = "--publish" ]; then
    shift
    state_dir=$(git -C "$REPO" rev-parse --absolute-git-dir)/claude-status || exit 1
    lock="$state_dir/lock"
    publish "$@"
    exit $?
fi

input=$(cat)
parsed=$(printf '%s' "$input" | parse_json) || parsed=""
{
    IFS= read -r version
    IFS= read -r model_id
    IFS= read -r display
    IFS= read -r ctx
    IFS= read -r hook_event
    IFS= read -r session_id
} <<EOF
$parsed
EOF

if [ -z "$version" ] && command -v claude >/dev/null 2>&1; then
    version=$(claude --version 2>/dev/null | awk '{print $1}')
fi
case $ctx in *[!0-9]* | "") ctx="" ;; esac

if [ -z "$hook_event" ]; then
    printf '%s · Claude Code %s\n' "$(pretty_model "$model_id" "$display" "$ctx")" "${version:-unknown}"
    source="status line"
else
    source="$hook_event hook"
fi

# Publish only complete snapshots from a clone we can find.
[ -n "$version" ] && [ -n "$model_id" ] || exit 0
git_dir=$(git -C "$REPO" rev-parse --absolute-git-dir 2>/dev/null) || exit 0
state_dir="$git_dir/claude-status"
mkdir -p "$state_dir/sessions" 2>/dev/null || exit 0

key="$version|$model_id|$display|$ctx|"
session_id=$(printf '%s' "$session_id" | tr -cd 'A-Za-z0-9_-')
session_file="$state_dir/sessions/${session_id:-default}"

# Publish when this session starts or changes model or version, not on every
# refresh. Two sessions on different models would otherwise take turns.
[ "$(cat "$session_file" 2>/dev/null)" = "$key" ] && exit 0
if [ "$(cat "$state_dir/published" 2>/dev/null)" = "$key" ]; then
    printf '%s' "$key" > "$session_file"
    exit 0
fi

# Back off after a failed attempt so an offline laptop does not retry on every refresh.
now=$(date +%s)
if [ -f "$state_dir/attempt" ]; then
    {
        IFS= read -r last_key
        IFS= read -r last_time
    } < "$state_dir/attempt"
    if [ "$last_key" = "$key" ] && [ $((now - ${last_time:-0})) -lt "$RETRY_SECONDS" ]; then
        exit 0
    fi
fi
printf '%s\n%s\n' "$key" "$now" > "$state_dir/attempt"

logfile="$state_dir/sync.log"
if [ -f "$logfile" ] && [ "$(wc -l < "$logfile")" -gt 500 ]; then
    tail -n 200 "$logfile" > "$logfile.tmp" && mv "$logfile.tmp" "$logfile"
fi
nohup "$script_path" --publish "$version" "$model_id" "$display" "$ctx" "$source" "$key" "$session_file" \
    </dev/null >>"$logfile" 2>&1 &
exit 0
