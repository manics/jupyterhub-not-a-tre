import os
import re

from kubernetes_asyncio.client.models import V1ServicePort
from kubespawner import KubeSpawner
from tornado.web import HTTPError
from traitlets import Unicode


def modify_pod_hook(spawner, pod):
    connection = os.getenv("GUACAMOLE_CONNECTION_TYPE")

    # First container is static-redirector, move user volume to user container
    pod.spec.containers[1].volume_mounts = pod.spec.containers[0].volume_mounts
    pod.spec.containers[0].volume_mounts = None

    # Move lifecycle hook to user container
    pod.spec.containers[1].lifecycle = pod.spec.containers[0].lifecycle
    pod.spec.containers[0].lifecycle = None

    chosen_profile = spawner.user_options.get("profile", "")
    if connection == "vnc":
        pod.spec.containers[1].command = ["start-tigervnc.sh"]
    elif connection == "rdp":
        pod.spec.containers[1].command = ["start-xrdp.sh"]
    else:
        raise ValueError(f"Invalid connection: {connection}")
    spawner.log.info(f"{chosen_profile=} {pod.spec.containers[1].command=}")
    return pod


class KubeSpawnerGuac(KubeSpawner):
    connection = Unicode("")

    def load_state(self, state):
        super().load_state(state)
        self.log.info(f"{state=}")
        state_connection = state.get("connection")
        if state_connection:
            if self.connection and self.connection != state_connection:
                self.log.error(
                    f"Mismatch: {self.connection=} {state_connection=}, not updating"
                )
            else:
                self.connection = state_connection

    def get_state(self):
        state = super().get_state()
        if self.connection:
            state["connection"] = self.connection
        self.log.info(f"{state=}")
        return state

    def get_service_manifest(self, owner_reference):
        service = super().get_service_manifest(owner_reference)
        service.spec.ports.append(
            V1ServicePort(name="rdp", port=3389, target_port=3389)
        )
        service.spec.ports.append(
            V1ServicePort(name="vnc", port=5901, target_port=5901)
        )
        return service


project_group_re = r"^project-[a-z0-9-]+$"
egress_admin_groupname = "egress-admins"
user_home_pvcname = "user-home-directories"
user_egress_pvcname = "user-egress-directories"
project_pvcname = "project-directories"
egress_pvcname = "airlock-egress-directories"


# https://discourse.jupyter.org/t/tailoring-spawn-options-and-server-configuration-to-certain-users/8449
async def custom_options_form(spawner):
    connection = os.getenv("GUACAMOLE_CONNECTION_TYPE")

    spawner.profile_list = []
    username = spawner.user.name

    for group in spawner.user.groups:
        groupname = group.name
        if re.match(project_group_re, groupname):
            spawner.log.info(f"Adding {groupname} project storage for {username}.")
            spawner.profile_list.append(
                {
                    "display_name": groupname,
                    "slug": groupname,
                    "kubespawner_override": {
                        "connection": connection,
                        "volumes": {
                            "home": {
                                "name": "home",
                                "persistentVolumeClaim": {
                                    "claimName": user_home_pvcname,
                                },
                            },
                            "project": {
                                "name": "project",
                                "persistentVolumeClaim": {
                                    "claimName": project_pvcname,
                                },
                            },
                            "egress": {
                                "name": "egress",
                                "persistentVolumeClaim": {
                                    "claimName": user_egress_pvcname,
                                },
                            },
                        },
                        "volume_mounts": {
                            "home": {
                                "name": "home",
                                "mountPath": f"/home/ubuntu",
                                "subPath": f"{groupname}/{username}",
                            },
                            "project": {
                                "name": "project",
                                "mountPath": f"/home/ubuntu/{groupname}",
                                "subPath": groupname,
                            },
                            "egress": {
                                "name": "egress",
                                "mountPath": f"/home/ubuntu/egress",
                                "subPath": f"{groupname}/{username}",
                            },
                        },
                    },
                }
            )

        if groupname == egress_admin_groupname:
            spawner.log.info(f"Adding {groupname} readonly storage for {username}.")
            spawner.profile_list.append(
                {
                    "display_name": groupname,
                    "slug": groupname,
                    "kubespawner_override": {
                        "connection": connection,
                        "volumes": {
                            "home": {
                                "name": "home",
                                "persistentVolumeClaim": {
                                    "claimName": user_home_pvcname,
                                },
                            },
                            "egress-review": {
                                "name": "egress-review",
                                "persistentVolumeClaim": {
                                    "claimName": egress_pvcname,
                                },
                            },
                        },
                        "volume_mounts": {
                            "home": {
                                "name": "home",
                                "mountPath": f"/home/ubuntu",
                                "subPath": f"{groupname}/{username}",
                            },
                            "egress-review": {
                                "name": "egress-review",
                                "mountPath": f"/home/ubuntu/egress-review",
                                "readOnly": True,
                            },
                        },
                    },
                }
            )

    if not spawner.profile_list:
        raise HTTPError(500, "No profiles found")
    return spawner._options_form_default()


c.KubeSpawner.modify_pod_hook = modify_pod_hook
c.JupyterHub.spawner_class = KubeSpawnerGuac
c.KubeSpawner.options_form = custom_options_form
