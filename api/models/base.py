"""Declarative base for every ORM model.

The schema is PRD section 4.2 verbatim. Column names are part of the API
contract (section 5), so they are not renamed for Python taste.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
