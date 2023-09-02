---
title: "[LeetCode (Easy)] 217. Contains Duplicate - Arrays and Hashmaps"
date: 2023-09-02 21:46:00 +0900
categories: [LeetCode, Blind75, Easy]
tags: [blind75, easy, leetcode, python, coding]
---


<h2><a href="https://leetcode.com/problems/contains-duplicate/">217. Contains Duplicate</a></h2><h3>Easy</h3><hr><div><p>Given an integer array <code>nums</code>, return <code>true</code> if any value appears <strong>at least twice</strong> in the array, and return <code>false</code> if every element is distinct.</p>

<p>&nbsp;</p>
<p><strong>Example 1:</strong></p>
<pre><strong>Input:</strong> nums = [1,2,3,1]
<strong>Output:</strong> true
</pre><p><strong>Example 2:</strong></p>
<pre><strong>Input:</strong> nums = [1,2,3,4]
<strong>Output:</strong> false
</pre><p><strong>Example 3:</strong></p>
<pre><strong>Input:</strong> nums = [1,1,1,3,3,4,3,2,4,2]
<strong>Output:</strong> true
</pre>
<p>&nbsp;</p>
<p><strong>Constraints:</strong></p>

<ul>
	<li><code>1 &lt;= nums.length &lt;= 10<sup>5</sup></code></li>
	<li><code>-10<sup>9</sup> &lt;= nums[i] &lt;= 10<sup>9</sup></code></li>
</ul>
</div>

```python
class Solution:
    def containsDuplicate(self, nums: List[int]) -> bool:
        hashMap = set()
        
        for i in nums:
            if i in hashMap:
                return True
            hashMap.add(i)
        return False

```