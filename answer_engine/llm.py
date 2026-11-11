"""The one place that calls the hosted model: the figure descriptions, the router, the answer and the judge."""
from openai import OpenAI

from . import config  # noqa: F401  (loads .env before the client reads OPENAI_API_KEY / OPENAI_BASE_URL)

client = OpenAI()


def parse(model, instructions, input, schema):
    """One call whose reply must match the pydantic `schema`; returns the parsed object."""
    reply = client.responses.parse(model=model, instructions=instructions, input=input, text_format=schema).output_parsed
    if reply is None:                              # e.g. a refusal: no JSON to parse
        raise ValueError("the model returned no parsable reply")
    return reply
