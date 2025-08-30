"""Common interfaces and data models for the paper notification system."""

from datetime import datetime

from pydantic import BaseModel


class Paper(BaseModel):
    """Generic paper representation for any academic paper source."""

    id: str
    title: str
    summary: str
    authors: list[str]
    published: datetime
    updated: datetime
    link: str
    categories: list[str]
