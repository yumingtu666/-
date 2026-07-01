# 经济日报（基金小白版）

这是一套面向基金投资新手的自动化财经资讯解读程序。它会在工作日早上 8 点抓取主流宏观财经资讯，筛选 3-5 条核心内容，并生成两种简报：

- 文字版：适合邮件、飞书、企业微信等渠道推送。
- 图片适配版：生成手机阅读友好的精简 Markdown，并在安装 Pillow 时额外输出 PNG 图片。

所有内容只做财经信息解读和基金知识科普，不提供股票、基金买卖、加仓减仓或择时建议。

## 功能覆盖

- 资讯方向：CPI、PMI、汇率、美债、市场流动性、行业政策、大类资产动态。
- 每条资讯固定包含 5 项：
  - 事件本身
  - 零基础大白话翻译
  - 对公募基金整体的影响逻辑
  - 受影响的基金品类/行业方向
  - 1 句极简记忆要点
- 标注信息属性：
  - 短期市场情绪影响
  - 中长期需要持续跟踪的核心信号
- 区分影响品类：
  - A股
  - 港股
  - 美股/QDII
  - 债券
  - 黄金

## 本地运行

```powershell
pip install -r requirements.txt
python src/daily_finance_brief.py
```

输出文件会生成在 `output/`：

- `YYYY-MM-DD-brief.md`
- `YYYY-MM-DD-mobile.md`
- `YYYY-MM-DD-mobile.png`，如果当前环境不支持图片生成，则输出 `YYYY-MM-DD-mobile.html`

## GitHub Actions 定时运行

已内置 `.github/workflows/daily-brief.yml`。

触发规则：

- 工作日：周一到周五
- 时间：北京时间 08:00
- GitHub cron：`0 0 * * 1-5`

也可以在 GitHub Actions 页面手动运行 `workflow_dispatch`。

## 数据源配置

数据源在 `config/sources.json` 中维护。默认使用 RSS/XML 数据源，后续可以替换或追加为你偏好的媒体、机构或内部资讯源。

```json
{
  "rss_sources": [
    {
      "name": "CNBC Finance",
      "url": "https://www.cnbc.com/id/10000664/device/rss/rss.html"
    }
  ],
  "max_news": 5,
  "lookback_hours": 36,
  "output_dir": "output"
}
```

如果某个数据源临时不可用，程序会跳过该源并继续处理其他来源。

## 内容边界

程序会避免输出以下内容：

- 明确买入、卖出、加仓、减仓建议
- 单条新闻推导投资结论
- 制造市场焦虑的夸张表达

建议把它定位为“每天帮小白读懂市场在说什么”的知识工具，而不是投资决策工具。
