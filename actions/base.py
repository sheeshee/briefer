from abc import ABC, abstractmethod

from core.models import Item


class BaseAction(ABC):

    action_id: str

    @abstractmethod
    def execute(self, item: Item) -> None:
        """
        Perform an action on the given item.
        """
        ...
