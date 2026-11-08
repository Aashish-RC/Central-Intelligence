"""Note Parser: Markdown frontmatter extraction, wiki-links scanning, and slug generation."""

import re
from typing import Any, Dict, List, Set, Tuple


WIKILINK_REGEX = re.compile(r"\[\[([^\|\]]+)(?:\|([^\]]+))?\]\]")
HASHTAG_REGEX = re.compile(r"(?:^|\s)#([a-zA-Z0-9_\-]+)")
FRONTMATTER_REGEX = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


class NoteParser:
    """Parses markdown content for metadata frontmatter, tags, and wiki-links."""

    @staticmethod
    def slugify(title: str) -> str:
        """Convert a title into an ASCII slug."""
        clean = re.sub(r"[^\w\s-]", "", title.lower())
        return re.sub(r"[-\s]+", "-", clean).strip("-")

    @classmethod
    def parse(cls, raw_content: str) -> Tuple[str, Dict[str, Any], List[str], List[str]]:
        """Parse raw markdown input.
        
        Returns:
            Tuple of:
            - body: Markdown text with frontmatter stripped
            - metadata: Extracted frontmatter key-values
            - tags: Unified list of frontmatter tags and inline #tags
            - outgoing_links: List of target note titles referenced via [[wiki-links]]
        """
        metadata: Dict[str, Any] = {}
        body = raw_content

        # 1. Frontmatter extraction
        fm_match = FRONTMATTER_REGEX.match(raw_content)
        if fm_match:
            fm_text = fm_match.group(1)
            body = raw_content[fm_match.end():]
            metadata = cls._parse_simple_yaml(fm_text)

        # 2. Extract inline #tags
        inline_tags: Set[str] = set()
        for m in HASHTAG_REGEX.finditer(body):
            inline_tags.add(m.group(1).lower())

        # Combine with metadata tags
        meta_tags = metadata.get("tags", [])
        if isinstance(meta_tags, str):
            meta_tags = [t.strip().lower() for t in meta_tags.split(",") if t.strip()]
        elif isinstance(meta_tags, list):
            meta_tags = [str(t).strip().lower() for t in meta_tags if str(t).strip()]
        else:
            meta_tags = []

        all_tags = sorted(list(set(meta_tags).union(inline_tags)))

        # 3. Extract wiki-links [[Target]]
        outgoing_links: List[str] = []
        for match in WIKILINK_REGEX.finditer(body):
            target = match.group(1).strip()
            if target and target not in outgoing_links:
                outgoing_links.append(target)

        return body, metadata, all_tags, outgoing_links

    @staticmethod
    def _parse_simple_yaml(text: str) -> Dict[str, Any]:
        """Simple lightweight key-value YAML parser without heavy dependencies."""
        data: Dict[str, Any] = {}
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                key, val = line.split(":", 1)
                key = key.strip()
                val = val.strip()
                # Array syntax [a, b, c]
                if val.startswith("[") and val.endswith("]"):
                    inner = val[1:-1].strip()
                    items = [i.strip().strip("'\"") for i in inner.split(",") if i.strip()]
                    data[key] = items
                # Quoted string
                elif (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                    data[key] = val[1:-1]
                # Booleans
                elif val.lower() in ("true", "false"):
                    data[key] = val.lower() == "true"
                # Integers
                elif val.isdigit():
                    data[key] = int(val)
                else:
                    data[key] = val
        return data
