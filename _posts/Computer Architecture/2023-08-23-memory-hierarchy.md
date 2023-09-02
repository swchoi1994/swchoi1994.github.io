---
title: "[Computer Architecture] Memory Hierarchy"
date: 2023-08-23 02:54:00 +0900
categories: [Computer Architecture]
tags: [computer architecture, arm, x86, amd, nvidia]
---

# [Computer Architecture] Memory Hierarchy

[문제 링크](https://school.programmers.co.kr/learn/courses/30/lessons/120583)

### 성능 요약

메모리: 10.1 MB, 시간: 0.01 ms

### 구분

코딩테스트 연습 > 코딩테스트 입문

### 채점결과

<br/>정확성: 100.0<br/>합계: 100.0 / 100.0

### 문제 설명

<p>정수가 담긴 배열 <code>array</code>와 정수 <code>n</code>이 매개변수로 주어질 때, <code>array</code>에 <code>n</code>이 몇 개 있는 지를 return 하도록 solution 함수를 완성해보세요.</p>

<hr>

<h5>제한사항</h5>

<ul>
<li>1 ≤ <code>array</code>의 길이 ≤ 100</li>
<li>0 ≤ <code>array</code>의 원소 ≤ 1,000</li>
<li>0 ≤ <code>n</code> ≤ 1,000</li>
</ul>

<hr>

<h5>입출력 예</h5>

| array              | n | result |
|--------------------|---|--------|
| [1, 1, 2, 3, 4, 5] | 1 | 2      |
| [0, 2, 3, 4]       | 1 | 0      |

<hr>

<h5>입출력 예 설명</h5>

<p>입출력 예 #1</p>

<ul>
<li>[1, 1, 2, 3, 4, 5] 에는 1이 2개 있습니다.</li>
</ul>

<p>입출력 예 #2</p>

<ul>
<li>[0, 2, 3, 4] 에는 1이 0개 있습니다.</li>
</ul>

### 정답

```python
def solution(array, n):
    answer = 0
    for i in range(len(array)):
        if array[i] == n:
            answer += 1
    return answer
```

<br>

> 출처: Meta AI Research, https://programmers.co.kr/learn/challenges
