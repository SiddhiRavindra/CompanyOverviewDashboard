from bs4 import BeautifulSoup

def html_to_structured_text(html: str) -> str:
    """
    Returns a simple, sectioned text format:
    # <H1>
    ## <H2>
    ### <H3>
    <paragraphs...>

    If no headings exist, falls back to whole-page text.
    """
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script","style","noscript"]):
        t.decompose()

    # Collect headings and following paragraphs until next heading
    lines = []
    # Order of headings we consider as “section boundaries”
    heading_tags = ["h1","h2","h3"]

    # If there are headings, chunk by them
    heads = soup.find_all(heading_tags)
    if heads:
        for h in heads:
            tag = h.name.lower()
            prefix = "#" * (heading_tags.index(tag) + 1)
            title = h.get_text(" ", strip=True)
            if title:
                lines.append(f"{prefix} {title}")

            # Pull contiguous siblings until next heading
            for sib in h.next_siblings:
                if getattr(sib, "name", None) in heading_tags:
                    break
                if getattr(sib, "name", None) in ["p","li","blockquote"]:
                    txt = sib.get_text(" ", strip=True)
                    if txt:
                        lines.append(txt)
    else:
        # fallback: plain text with light normalization
        raw = soup.get_text("\n")
        chunks = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        lines.extend(chunks)

    return "\n".join(lines)
