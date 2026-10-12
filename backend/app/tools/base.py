from abc import abstractmethod

from langchain_core.tools import BaseTool


class BaseAgentTool(BaseTool):
    @abstractmethod
    def _run(self, *args, **kwargs) -> str:
        pass

    async def _arun(self, *args, **kwargs) -> str:
        return self._run(*args, **kwargs)
