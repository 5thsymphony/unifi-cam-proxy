import json
from typing import Any, Dict, Optional

from asyncio_mqtt import Client

from unifi.cams.base import SmartDetectObjectType
from unifi.cams.rtsp import RTSPCam


class FrigateCam(RTSPCam):
    def __init__(self, args, logger=None):
        super().__init__(args, logger)
        self.args = args
        self.event_active = False

    @classmethod
    def add_parser(self, parser):
        super().add_parser(parser)
        parser.add_argument("--mqtt-host", required=True, help="MQTT server")
        parser.add_argument("--mqtt-port", default=1883, type=int, help="MQTT server")
        parser.add_argument(
            "--mqtt-prefix", default="frigate", type=str, help="Topic prefix"
        )

    def get_feature_flags(self) -> Dict[str, Any]:
        return {
            "mic": True,
            "smartDetect": [
                "person",
                "vehicle",
            ],
        }

    @classmethod
    def label_to_object_type(cls, label: str) -> Optional[SmartDetectObjectType]:
        if label == "person":
            return SmartDetectObjectType.PERSON
        elif label == "car":
            return SmartDetectObjectType.CAR

    async def run(self):
        async with Client(self.args.mqtt_host, port=self.args.mqtt_port) as client:
            topic = f"{self.args.mqtt_prefix}/events"
            async with client.filtered_messages(topic) as messages:
                await client.subscribe(topic)
                async for message in messages:
                    msg = message.payload.decode()
                    try:
                        frigate_msg = json.loads(message.payload.decode())
                        label = frigate_msg["after"]["label"]
                        object_type = self.label_to_object_type(label)
                        if not object_type:
                            self.logger.warning(
                                f"Received unsupport detection label type: {label}"
                            )

                        if not self.event_active and frigate_msg["type"] == "new":
                            await self.trigger_motion_start(object_type)
                            self.event_active = True
                        elif self.event_active and frigate_msg["type"] == "end":
                            await self.trigger_motion_stop(object_type)
                            self.event_active = False
                    except ValueError:
                        self.logger.exception(f"Could not decode payload: {msg}")
