import re


class Parser:

    def parse(self, *args, **kwargs):
        raise NotImplementedError("Parse method must be implemented by subclasses")

    def _expand_range(self, pattern):
        match = re.search(r'\[(\d+)-(\d+)]', pattern)
        if match:
            prefix = pattern[:match.start()]
            start = int(match.group(1))
            end = int(match.group(2))
            suffix = pattern[match.end():]
            return [f'{prefix}{i}{suffix}' for i in range(start, end + 1)]
        else:
            return [pattern]
