# elaina-plugins-schulte

ElainaBot v2 插件 — 5×5 舒尔特方格反应力训练。
原项目:[舒尔特方格](https://github.com/MengXiaSS/elaina-plugin-shuerte)
原作者:孟夏十三

## 功能

- **开始训练**：生成 5×5 随机数字回调按钮，按 1→25 顺序点击
- **结束训练**：放弃当前对局
- **舒尔特排行**：全服 TOP10（每位用户保留最快成绩）

## web面板

- **数据展示**：显示前20名与最近20次训练
- **高自定义**：可修改配色、页脚内容、菜单指令

## 指令

| 指令 | 说明 |
|------|------|
| `开始训练` | 开始一局 |
| `结束训练` | 放弃当前对局 |
| `舒尔特排行` | 查看排行榜 |

## 数据

排行数据保存在插件目录 `data/ShuErTe.db`（SQLite，首次运行自动创建）。

## 框架要求

[ElainaBot v2](https://github.com/ElainaCore/ElainaBot_v2)