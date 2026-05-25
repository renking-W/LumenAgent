import uuid

from lumen_agent.api.routers.knowledge import _service
from lumen_agent.config import get_settings
import questionary
import readline
from pathlib import Path

settings = get_settings()

async def knowledge_operation():
    service = _service(settings)
    select_operation = questionary.select(
        "知识库管理",
        choices=["new_knowledge", "list_knowledge"],
    ).ask()
    if select_operation == "new_knowledge":
        knowledge_id=str(uuid.uuid4())
        source_name = input("为新知识取个名字吧:\n")
        knowledge_path = input("请输入知识文件路径:")
        result=await service.ingest_file(Path(knowledge_path), knowledge_id=knowledge_id)
