---
title: "{{ (replace (replace .Name (delimit (last 1 (split .Name "-")) "-") "") "-" " " ) | title }}"
year: "{{ index (last 1 (split .Name "-")) 0 }}"
date: "{{ now | dateFormat "2006-01-02" }}"
price: ""
theaters: [""]
seat: [""]
remark: [""]
---
