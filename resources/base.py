from abc import ABC, abstractmethod


class BaseResource(ABC):

    source_id: str

    @abstractmethod
    def fetch(self, user) -> None:
        """
        Fetch items from the source and write them to the database for the given user.
        Must be idempotent — use (user, external_id) to avoid duplicates.
        """
        ...
