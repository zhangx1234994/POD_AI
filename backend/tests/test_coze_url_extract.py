from app.routers.coze_podi_plugin import _extract_urls_from_value


def test_extract_urls_keeps_comma_inside_single_url_query():
    value = "https://gips3.baidu.com/it/u=3886271102,3123389489&fm=3028&app=3028"
    assert _extract_urls_from_value(value) == [value]


def test_extract_urls_split_multiple_urls_by_comma_or_newline():
    value = "https://a.example.com/1.png,https://b.example.com/2.png\nhttps://c.example.com/3.png"
    assert _extract_urls_from_value(value) == [
        "https://a.example.com/1.png",
        "https://b.example.com/2.png",
        "https://c.example.com/3.png",
    ]
