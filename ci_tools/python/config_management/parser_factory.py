def to_camel_case(name):
    """
    Convert a string from snake_case to camelCase.
    Args:
        name (str): The string to be converted.
    Returns:
        str: The converted string.
    Raises:
        ValueError: If the input name is not a string.
    """
    if not isinstance(name, str):
        raise ValueError("Input 'name' must be a string")

    if not name:
        return ''

    if '_' not in name:
        return name

    return ''.join(word.capitalize() for word in name.split('_'))


class ParserFactory:
    _parsers = {}

    @classmethod
    def register_parser(cls, parser_cls):
        parser_name = to_camel_case(parser_cls.__name__).lower()
        cls._parsers[parser_name] = parser_cls

    @classmethod
    def get_parser(cls, parser_type):
        parser_class = cls._parsers.get(parser_type)
        if not parser_class:
            raise ValueError(f"Unknown parser type: {parser_type}")
        return parser_class()
