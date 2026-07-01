from __future__ import annotations

import argparse
import email.utils
import html
import json
import re
import textwrap
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable


CN_TZ = timezone(timedelta(hours=8))


TOPIC_RULES = [
    {
        "topic": "CPI / 通胀",
        "keywords": ["cpi", "inflation", "price index", "consumer price", "通胀", "物价", "cpi"],
        "assets": ["债券基金", "黄金相关基金", "美股/QDII基金", "A股宽基基金"],
        "attribute": "中长期核心信号",
        "impact": {
            "A股": "通胀会影响货币政策预期，间接影响股票估值和消费、资源等板块表现。",
            "港股": "港股对海外利率更敏感，通胀走向会影响资金风险偏好。",
            "美股/QDII": "美国通胀会影响美联储降息或加息预期，进而影响美股和QDII基金波动。",
            "债券": "通胀偏高时债券价格通常承压，通胀回落时债券基金环境相对友好。",
            "黄金": "通胀和实际利率预期会共同影响黄金相关资产。"
        },
    },
    {
        "topic": "PMI / 景气度",
        "keywords": ["pmi", "manufacturing", "services activity", "factory activity", "采购经理", "景气"],
        "assets": ["A股宽基基金", "周期行业基金", "制造业相关基金", "港股基金"],
        "attribute": "中长期核心信号",
        "impact": {
            "A股": "PMI像经济体温计，改善时市场更愿意相信企业盈利会变好。",
            "港股": "港股中顺周期和互联网消费板块会受经济预期影响。",
            "美股/QDII": "海外PMI影响全球增长预期，也会传导到QDII持仓资产。",
            "债券": "经济偏强时债券可能面临利率上行压力，经济偏弱时债券相对受关注。",
            "黄金": "景气转弱时避险需求可能上升，但还要看美元和利率。"
        },
    },
    {
        "topic": "汇率 / 美元",
        "keywords": ["yuan", "renminbi", "dollar", "currency", "exchange rate", "forex", "汇率", "人民币", "美元"],
        "assets": ["QDII基金", "港股基金", "黄金相关基金", "出口链基金"],
        "attribute": "短期市场情绪影响",
        "impact": {
            "A股": "汇率会影响外资情绪和出口企业利润预期。",
            "港股": "港股资金面与美元流动性关系较近，汇率波动容易放大情绪。",
            "美股/QDII": "QDII基金净值会同时受海外资产价格和汇率折算影响。",
            "债券": "汇率压力可能影响资金面和政策预期，但通常不是债券唯一变量。",
            "黄金": "美元走强常会压制黄金价格，美元走弱时黄金相对受益。"
        },
    },
    {
        "topic": "美债 / 海外利率",
        "keywords": ["treasury", "yield", "bond yield", "fed rate", "interest rate", "美债", "收益率", "利率", "降息", "加息"],
        "assets": ["债券基金", "港股基金", "美股/QDII基金", "黄金相关基金", "成长风格基金"],
        "attribute": "中长期核心信号",
        "impact": {
            "A股": "海外利率会影响全球资金偏好，成长股估值尤其敏感。",
            "港股": "港股估值受海外利率影响较明显，美债收益率下行通常有助于风险偏好修复。",
            "美股/QDII": "美债收益率变化会直接影响美股估值，尤其是科技成长方向。",
            "债券": "国内债券主要看国内利率，但海外利率会影响跨境资金和政策预期。",
            "黄金": "实际利率下降通常有利于黄金，实际利率上升则可能压制黄金。"
        },
    },
    {
        "topic": "流动性 / 央行政策",
        "keywords": ["liquidity", "central bank", "pboc", "federal reserve", "repo", "money market", "央行", "流动性", "逆回购", "降准", "mlf"],
        "assets": ["债券基金", "A股宽基基金", "港股基金", "货币基金"],
        "attribute": "短期市场情绪影响",
        "impact": {
            "A股": "资金面宽松时，市场交易情绪通常更稳。",
            "港股": "港股对全球资金松紧较敏感，流动性改善有助于估值修复。",
            "美股/QDII": "海外央行政策会影响美股和QDII基金的估值环境。",
            "债券": "流动性宽松通常有利于债券价格和货币基金收益稳定。",
            "黄金": "宽松预期可能压低实际利率，对黄金形成支撑。"
        },
    },
    {
        "topic": "行业政策",
        "keywords": ["policy", "subsidy", "regulation", "tariff", "industrial", "政策", "补贴", "监管", "产业"],
        "assets": ["新能源基金", "半导体基金", "医药基金", "消费基金", "港股互联网基金"],
        "attribute": "中长期核心信号",
        "impact": {
            "A股": "行业政策会改变某些板块的盈利预期和估值想象空间。",
            "港股": "港股中互联网、医药、消费等板块对监管和产业政策较敏感。",
            "美股/QDII": "海外产业政策会影响科技、能源、医药等主题QDII。",
            "债券": "行业政策对债券基金影响较间接，主要看是否改变信用风险。",
            "黄金": "行业政策对黄金通常不是主变量。"
        },
    },
    {
        "topic": "大类资产动态",
        "keywords": ["stocks", "equities", "oil", "gold", "commodities", "market", "risk appetite", "股市", "原油", "黄金", "商品"],
        "assets": ["A股宽基基金", "港股基金", "美股/QDII基金", "黄金相关基金", "商品基金"],
        "attribute": "短期市场情绪影响",
        "impact": {
            "A股": "大类资产波动会影响市场情绪，但需要结合国内基本面判断。",
            "港股": "港股弹性较大，容易受全球风险偏好影响。",
            "美股/QDII": "海外股债商品波动会直接影响QDII基金净值。",
            "债券": "风险偏好下降时，债券类资产常被用来平衡波动。",
            "黄金": "避险情绪和美元利率变化都会影响黄金。"
        },
    },
]


@dataclass
class NewsItem:
    title: str
    summary: str
    link: str
    source: str
    published: datetime


def strip_tags(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value or "")
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def parse_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    try:
        parsed = email.utils.parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def fetch_url(url: str, timeout: int = 20) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; daily-finance-brief/1.0; +https://github.com/)",
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def text_of(parent: ET.Element, names: Iterable[str]) -> str:
    for name in names:
        found = parent.find(name)
        if found is not None and found.text:
            return strip_tags(found.text)
    for child in parent:
        tag = child.tag.split("}")[-1].lower()
        if tag in {n.lower() for n in names} and child.text:
            return strip_tags(child.text)
    return ""


def parse_feed(xml_bytes: bytes, source_name: str) -> list[NewsItem]:
    root = ET.fromstring(xml_bytes)
    items = root.findall(".//item")
    if not items:
        items = root.findall(".//{http://www.w3.org/2005/Atom}entry")

    parsed: list[NewsItem] = []
    for item in items:
        title = text_of(item, ["title"])
        summary = text_of(item, ["description", "summary", "content"])
        link = text_of(item, ["link"])
        if not link:
            link_element = item.find("{http://www.w3.org/2005/Atom}link")
            link = link_element.attrib.get("href", "") if link_element is not None else ""
        published_raw = text_of(item, ["pubDate", "published", "updated"])
        if title:
            parsed.append(
                NewsItem(
                    title=title,
                    summary=summary,
                    link=link,
                    source=source_name,
                    published=parse_datetime(published_raw),
                )
            )
    return parsed


def classify(item: NewsItem) -> tuple[dict, int]:
    haystack = f"{item.title} {item.summary}".lower()
    best_rule = TOPIC_RULES[-1]
    best_score = 0
    for rule in TOPIC_RULES:
        score = sum(1 for keyword in rule["keywords"] if keyword.lower() in haystack)
        if score > best_score:
            best_rule = rule
            best_score = score
    return best_rule, best_score


def plain_language(topic: str, title: str) -> str:
    explainers = {
        "CPI / 通胀": "可以把它理解成一篮子日常商品和服务的涨价速度。涨得太快，钱会变得不那么耐花，政策通常会更谨慎。",
        "PMI / 景气度": "它像企业订单和生产的体温计。高于荣枯线通常表示经济活动更活跃，低迷则说明企业信心偏弱。",
        "汇率 / 美元": "汇率就是不同货币之间的兑换价格。它会影响海外资产折算回人民币后的表现，也会影响外资情绪。",
        "美债 / 海外利率": "美债收益率可以理解成全球资金的参考利率。它上升时，很多风险资产会觉得压力变大。",
        "流动性 / 央行政策": "流动性就是市场里钱紧不紧。钱更充裕时，资产价格更容易稳定；钱偏紧时，波动往往会放大。",
        "行业政策": "政策会改变一个行业未来赚钱的环境。支持力度更大时，行业预期可能改善；监管更严时，估值会更谨慎。",
        "大类资产动态": "股、债、商品、黄金之间会互相影响。某一类资产大幅波动，常常反映资金正在重新选择方向。",
    }
    return explainers.get(topic, f"这条消息的核心是：{title}。先看它改变了什么，再看它影响哪些资产。")


def fund_logic(rule: dict) -> str:
    if rule["topic"] == "CPI / 通胀":
        return "公募基金会受两条线影响：一是通胀改变利率预期，二是不同板块成本和售价受到影响。"
    if rule["topic"] == "PMI / 景气度":
        return "基金净值背后是企业盈利和市场情绪。景气改善时，权益类基金更容易获得关注；景气走弱时，债券和稳健类资产更受重视。"
    if rule["topic"] == "汇率 / 美元":
        return "汇率会影响跨境资金流向和QDII基金的人民币计价净值，也会影响出口、黄金、港股等方向的情绪。"
    if rule["topic"] == "美债 / 海外利率":
        return "海外利率像资产定价的锚，利率上行会压低高估值资产吸引力，利率下行则可能缓和估值压力。"
    if rule["topic"] == "流动性 / 央行政策":
        return "资金面宽松通常有利于债券和权益市场情绪，资金面偏紧时基金短期波动可能加大。"
    if rule["topic"] == "行业政策":
        return "主题基金和行业基金更容易受到政策影响，因为它们的持仓集中，行业预期变化会更快反映到净值里。"
    return "大类资产变化会影响基金的持仓资产价格，也会影响投资者对风险的接受程度。"


def memory_point(rule: dict) -> str:
    points = {
        "CPI / 通胀": "记住：通胀看的是物价压力，关键会传导到利率和债券。",
        "PMI / 景气度": "记住：PMI像经济体温计，冷热会影响权益基金情绪。",
        "汇率 / 美元": "记住：汇率变动会让跨境基金多一层波动。",
        "美债 / 海外利率": "记住：美债收益率越受关注，成长和QDII越要看它脸色。",
        "流动性 / 央行政策": "记住：市场里的钱松不松，会影响短期波动。",
        "行业政策": "记住：主题基金看政策，政策改变行业预期。",
        "大类资产动态": "记住：股债商品一起看，才能知道资金偏好在哪里。",
    }
    return points.get(rule["topic"], "记住：先分清消息影响的是情绪，还是基本面。")


def objective_event(item: NewsItem) -> str:
    date_text = item.published.astimezone(CN_TZ).strftime("%Y-%m-%d")
    summary = item.summary
    if len(summary) > 120:
        summary = summary[:117] + "..."
    if summary:
        return f"{date_text}，{item.source}发布/报道：{item.title}。{summary}"
    return f"{date_text}，{item.source}发布/报道：{item.title}。"


def build_interpretation(item: NewsItem) -> dict:
    rule, score = classify(item)
    return {
        "title": item.title,
        "source": item.source,
        "link": item.link,
        "published": item.published.astimezone(CN_TZ).strftime("%Y-%m-%d %H:%M"),
        "topic": rule["topic"],
        "attribute": rule["attribute"],
        "objective": objective_event(item),
        "plain": plain_language(rule["topic"], item.title),
        "fund_logic": fund_logic(rule),
        "assets": "、".join(rule["assets"]),
        "memory": memory_point(rule),
        "market_impact": rule["impact"],
        "score": score,
    }


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def collect_news(config: dict) -> list[NewsItem]:
    items: list[NewsItem] = []
    for source in config["rss_sources"]:
        try:
            items.extend(parse_feed(fetch_url(source["url"]), source["name"]))
        except Exception as exc:
            print(f"[warn] 跳过数据源 {source['name']}: {exc}")
    return items


def select_core_items(items: list[NewsItem], max_news: int, lookback_hours: int) -> list[NewsItem]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    recent = [item for item in items if item.published >= cutoff]
    if not recent:
        recent = sorted(items, key=lambda item: item.published, reverse=True)[: max_news * 2]

    ranked = []
    for item in recent:
        rule, score = classify(item)
        recency_bonus = max(0, int((item.published - cutoff).total_seconds() // 3600))
        ranked.append((score * 100 + recency_bonus, rule["topic"], item))

    selected: list[NewsItem] = []
    used_topics: set[str] = set()
    for _, topic, item in sorted(ranked, key=lambda value: value[0], reverse=True):
        if topic not in used_topics or len(selected) >= 3:
            selected.append(item)
            used_topics.add(topic)
        if len(selected) >= max_news:
            break
    return selected


def render_text_brief(items: list[dict], report_date: datetime) -> str:
    date_text = report_date.astimezone(CN_TZ).strftime("%Y年%m月%d日")
    lines = [
        f"# 基金小白财经简报｜{date_text}",
        "",
        "说明：本简报只做财经信息解读和基金知识科普，不提供任何股票/基金买卖、加仓减仓或择时建议。",
        "",
        "## 今日核心信息",
    ]
    for index, item in enumerate(items, 1):
        lines.extend(
            [
                "",
                f"### {index}. {item['topic']}｜{item['title']}",
                f"- 信息属性：{item['attribute']}",
                f"- 来源时间：{item['source']}｜{item['published']}",
                f"- ① 事件本身：{item['objective']}",
                f"- ② 大白话翻译：{item['plain']}",
                f"- ③ 对公募基金的影响逻辑：{item['fund_logic']}",
                f"- ④ 可能受影响的基金品类/方向：{item['assets']}",
                f"- ⑤ 极简记忆点：{item['memory']}",
                "- 分品类影响：",
            ]
        )
        for market, impact in item["market_impact"].items():
            lines.append(f"  - {market}：{impact}")
        if item["link"]:
            lines.append(f"- 原文链接：{item['link']}")

    lines.extend(
        [
            "",
            "## 风险提示",
            "宏观资讯对基金的影响通常需要和估值、业绩、政策、资金面一起观察。单条新闻不等于投资结论，也不构成任何投资建议。",
        ]
    )
    return "\n".join(lines) + "\n"


def render_mobile_brief(items: list[dict], report_date: datetime) -> str:
    date_text = report_date.astimezone(CN_TZ).strftime("%m月%d日")
    lines = [
        f"# {date_text} 基金小白财经简报",
        "",
        "只解读，不建议买卖。",
        "",
    ]
    for index, item in enumerate(items, 1):
        lines.extend(
            [
                f"## {index}. {item['topic']}",
                f"**属性**：{item['attribute']}",
                f"**发生了什么**：{item['title']}",
                f"**小白版**：{item['plain']}",
                f"**影响方向**：{item['assets']}",
                f"**一句话**：{item['memory']}",
                "",
            ]
        )
    return "\n".join(lines)


def wrap_text(draw, text: str, font, max_width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.splitlines():
        if not paragraph:
            lines.append("")
            continue
        current = ""
        for char in paragraph:
            trial = current + char
            bbox = draw.textbbox((0, 0), trial, font=font)
            if bbox[2] - bbox[0] <= max_width:
                current = trial
            else:
                if current:
                    lines.append(current)
                current = char
        if current:
            lines.append(current)
    return lines


def render_image(mobile_text: str, output_path: Path) -> bool:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return False

    width = 1080
    margin = 64
    bg = "#f8fafc"
    ink = "#172033"
    muted = "#5b6472"
    accent = "#006d77"
    font_paths = [
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]

    def font(size: int, bold: bool = False):
        candidates = font_paths
        for path in candidates:
            if Path(path).exists():
                return ImageFont.truetype(path, size=size)
        return ImageFont.load_default()

    title_font = font(46, True)
    heading_font = font(34, True)
    body_font = font(28)
    small_font = font(23)

    temp = Image.new("RGB", (width, 10), bg)
    draw = ImageDraw.Draw(temp)
    content_lines = []
    for raw_line in mobile_text.splitlines():
        if raw_line.startswith("# "):
            content_lines.append(("title", raw_line[2:]))
        elif raw_line.startswith("## "):
            content_lines.append(("heading", raw_line[3:]))
        elif raw_line.startswith("**"):
            clean = raw_line.replace("**", "")
            content_lines.extend(("body", line) for line in wrap_text(draw, clean, body_font, width - margin * 2))
        elif raw_line:
            content_lines.extend(("small", line) for line in wrap_text(draw, raw_line, small_font, width - margin * 2))
        else:
            content_lines.append(("space", ""))

    heights = {"title": 64, "heading": 52, "body": 42, "small": 34, "space": 22}
    height = margin * 2 + sum(heights[kind] for kind, _ in content_lines) + 80
    image = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(image)
    y = margin
    draw.rounded_rectangle((36, 36, width - 36, height - 36), radius=28, fill="#ffffff", outline="#d9e2ec", width=2)
    for kind, line in content_lines:
        if kind == "space":
            y += heights[kind]
            continue
        active_font = {"title": title_font, "heading": heading_font, "body": body_font, "small": small_font}[kind]
        color = accent if kind in {"title", "heading"} else ink if kind == "body" else muted
        draw.text((margin, y), line, font=active_font, fill=color)
        y += heights[kind]
    draw.text((margin, height - margin - 8), "仅作财经科普，不构成投资建议", font=small_font, fill="#8a94a3")
    image.save(output_path)
    return True


def render_html(mobile_text: str, output_path: Path) -> None:
    body = html.escape(mobile_text)
    body = re.sub(r"^# (.+)$", r"<h1>\1</h1>", body, flags=re.MULTILINE)
    body = re.sub(r"^## (.+)$", r"<h2>\1</h2>", body, flags=re.MULTILINE)
    body = body.replace("**", "")
    body = body.replace("\n", "<br>\n")
    output_path.write_text(
        f"""<!doctype html>
<html lang="zh-CN">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>基金小白财经简报</title>
<style>
body {{ margin: 0; background: #f8fafc; color: #172033; font-family: -apple-system, BlinkMacSystemFont, "Microsoft YaHei", sans-serif; }}
.page {{ max-width: 640px; margin: 0 auto; padding: 28px; }}
.card {{ background: #fff; border: 1px solid #d9e2ec; border-radius: 8px; padding: 28px; }}
h1 {{ color: #006d77; font-size: 30px; line-height: 1.25; margin: 0 0 16px; }}
h2 {{ color: #006d77; font-size: 22px; margin: 26px 0 10px; }}
body, .card {{ font-size: 17px; line-height: 1.72; }}
.note {{ color: #8a94a3; font-size: 14px; margin-top: 24px; }}
</style>
<div class="page"><div class="card">{body}<div class="note">仅作财经科普，不构成投资建议</div></div></div>
</html>
""",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a novice-friendly daily finance brief.")
    parser.add_argument("--config", default="config/sources.json")
    parser.add_argument("--date", default=None, help="Report date, YYYY-MM-DD. Defaults to today in Asia/Shanghai.")
    args = parser.parse_args()

    root = Path.cwd()
    config = load_config(root / args.config)
    output_dir = root / config.get("output_dir", "output")
    output_dir.mkdir(parents=True, exist_ok=True)

    report_date = (
        datetime.strptime(args.date, "%Y-%m-%d").replace(tzinfo=CN_TZ)
        if args.date
        else datetime.now(CN_TZ)
    )

    news = collect_news(config)
    selected = select_core_items(news, int(config.get("max_news", 5)), int(config.get("lookback_hours", 36)))
    if not selected:
        raise SystemExit("未抓取到可用资讯，请检查数据源配置。")

    interpreted = [build_interpretation(item) for item in selected]
    date_slug = report_date.strftime("%Y-%m-%d")
    text_brief = render_text_brief(interpreted, report_date)
    mobile_brief = render_mobile_brief(interpreted, report_date)

    text_path = output_dir / f"{date_slug}-brief.md"
    mobile_md_path = output_dir / f"{date_slug}-mobile.md"
    image_path = output_dir / f"{date_slug}-mobile.png"
    html_path = output_dir / f"{date_slug}-mobile.html"

    text_path.write_text(text_brief, encoding="utf-8")
    mobile_md_path.write_text(mobile_brief, encoding="utf-8")
    if not render_image(mobile_brief, image_path):
        render_html(mobile_brief, html_path)

    print(f"文字版: {text_path}")
    print(f"图片适配版Markdown: {mobile_md_path}")
    if image_path.exists():
        print(f"图片版: {image_path}")
    else:
        print(f"图片适配HTML: {html_path}")


if __name__ == "__main__":
    main()
