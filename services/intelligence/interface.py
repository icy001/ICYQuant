from abc import ABC, abstractmethod


class IntelligenceModule(ABC):

    @abstractmethod
    def run(self, context):

        pass
