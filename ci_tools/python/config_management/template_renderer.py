import json

import yaml
from jinja2 import Template
from python.common.basic_logger import get_logger

logger = get_logger()


class TemplateRenderer:
    def __init__(self):
        self.rendered_result = None

    def render_template(self, template_str, context):
        # template_str = FileManager.read_file(self.file_path)
        if not template_str:
            return {}
        template = Template(template_str)
        logger.debug(f"Rendering config templates, template_str: {template_str}, context:{context}")
        self.rendered_result = template.render(context)
        return self

    def decode_result(self, decoder="json"):
        if not self.rendered_result:
            raise Exception("render_template first")
        if decoder == "json":
            return json.loads(self.rendered_result)
        elif decoder == "yaml":
            return yaml.safe_load(self.rendered_result)
        else:
            raise ValueError("Unsupported decoder specified")
