"""Common interfaces and data models for the paper notification system."""

from datetime import date, datetime

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


class LambdaEvent(BaseModel):
    """Lambda function event parameters."""

    inclusive_end_date: date | None = None


if __name__ == "__main__":
    print(LambdaEvent.model_validate({}))
