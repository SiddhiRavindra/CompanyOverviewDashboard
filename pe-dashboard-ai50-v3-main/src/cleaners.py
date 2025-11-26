from bs4 import BeautifulSoup

def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script","style","noscript"]): t.decompose()
    lines = [ln.strip() for ln in soup.get_text("\n").splitlines()]
    return "\n".join([ln for ln in lines if ln])
