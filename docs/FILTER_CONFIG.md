# 数据过滤配置

同步到佳明前可按健康指标过滤身体成分数据（体重、BMI、体脂率等）。过滤规则配置在每个用户的 `garmin.filter` 下，支持多用户各自独立配置。

---

## 配置方法

```json
{
    "users": [
        {
            "username": "您的手机号/邮箱",
            "model": "yunmai.scales.ms103",
            "garmin": {
                "email": "您的佳明账号",
                "domain": "CN",
                "filter": {
                    "enabled": true,
                    "conditions": [
                        { "field": "Weight", "operator": "between", "value": [60, 70] }
                    ],
                    "logic": "and"
                }
            }
        }
    ]
}
```

### 参数

`filter` 对象：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `enabled` | boolean | 否 | 是否启用过滤，默认 `true` |
| `conditions` | array | 是 | 过滤条件数组 |
| `logic` | string | 否 | 多条件逻辑关系，`"and"` 或 `"or"`，默认 `"and"` |

`condition` 对象：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `field` | string | 是 | 指标名（见下表） |
| `operator` | string | 是 | 比较操作符（见下表） |
| `value` | number / array | 是 | 比较值；`between` 为含边界的两值数组 |

### 支持的字段

| 字段 | 说明 | 类型 | 示例 |
|------|------|------|------|
| `Weight` | 体重 | float | 70.5 (kg) |
| `BMI` | 身体质量指数 | float | 23.8 |
| `BodyFat` | 体脂率 | float | 15.2 (%) |
| `BodyWater` | 体水率 | float | 58.3 (%) |
| `BoneMass` | 骨量 | float | 2.8 (kg) |
| `MetabolicAge` | 代谢年龄 | int | 28 (岁) |
| `MuscleMass` | 肌肉量 | float | 30.1 (kg) |
| `VisceralFat` | 内脏脂肪等级 | int | 5 |
| `BasalMetabolism` | 基础代谢 | int | 1650 (kcal) |

### 支持的操作符

| 操作符 | 含义 | 示例 |
|--------|------|------|
| `eq` | 等于 | `{ "field": "Weight", "operator": "eq", "value": 70 }` |
| `ne` | 不等于 | `{ "field": "Weight", "operator": "ne", "value": 70 }` |
| `gt` | 大于 | `{ "field": "Weight", "operator": "gt", "value": 70 }` |
| `gte` | 大于等于 | `{ "field": "Weight", "operator": "gte", "value": 60 }` |
| `lt` | 小于 | `{ "field": "Weight", "operator": "lt", "value": 80 }` |
| `lte` | 小于等于 | `{ "field": "Weight", "operator": "lte", "value": 70 }` |
| `between` | 区间（含边界） | `{ "field": "Weight", "operator": "between", "value": [60, 70] }` |

---

## 配置示例

只同步体重 60-70kg：

```json
"filter": {
    "enabled": true,
    "conditions": [
        { "field": "Weight", "operator": "between", "value": [60, 70] }
    ],
    "logic": "and"
}
```

体重 ≥ 60kg 且体脂率 < 25%（AND 组合）：

```json
"filter": {
    "enabled": true,
    "conditions": [
        { "field": "Weight", "operator": "gte", "value": 60 },
        { "field": "BodyFat", "operator": "lt", "value": 25 }
    ],
    "logic": "and"
}
```

体重 < 60kg 或 > 80kg（OR 组合，用于剔除正常范围）：

```json
"filter": {
    "enabled": true,
    "conditions": [
        { "field": "Weight", "operator": "lt", "value": 60 },
        { "field": "Weight", "operator": "gt", "value": 80 }
    ],
    "logic": "or"
}
```

BMI 正常范围（18.5-24）：

```json
"filter": {
    "enabled": true,
    "conditions": [
        { "field": "BMI", "operator": "between", "value": [18.5, 24] }
    ],
    "logic": "and"
}
```

禁用过滤（同步所有数据）：

```json
"filter": { "enabled": false }
```

或直接删除 `filter` 字段。

---

## 行为与兼容性

- `filter` 字段不存在 → 同步所有数据（默认行为）。
- `filter.enabled: false` → 过滤不生效。
- 过滤配置非法（字段/操作符/取值错误）→ 记录错误、跳过过滤、用原始数据继续同步，**不中断同步流程**。
- 全部数据被过滤掉 → 生成空 FIT 文件并记录警告；检查条件是否过严。

日志输出示例：

```
INFO - Weight filter enabled: 2 condition(s) with 'AND' logic
INFO - Applying weight filter with 2 condition(s) using 'AND' logic
INFO - Filter applied: 15/20 records passed (5 filtered out)
INFO - Filter reduced records from 20 to 15 (5 filtered out)
```

---

## 常见问题

**Q: 过滤配置错误会导致同步失败吗？**
不会。配置非法时跳过过滤，用原始数据同步并记录错误日志。

**Q: 可以为不同用户设置不同规则吗？**
可以。`filter` 挂在每个用户的 `garmin` 配置下，各用户独立。

**Q: 支持按时间范围过滤吗？**
当前版本不支持。需要此功能请提交 issue 或 PR。
