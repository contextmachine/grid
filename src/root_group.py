from mmcore.base import AGroup, adict, idict
from src.props import props_table
class RootGroup(AGroup):

    def props_update(self, uuids: list[str], props: dict):
        for uuid in uuids:
            props_table[uuid].set(props)

        return True
