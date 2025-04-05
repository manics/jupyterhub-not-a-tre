# Investigation into a Z2JH TRE

## Prerequisites

### Kubernetes, Helm, Host system

This is only tested with a [default K3s Kubernetes installation](https://docs.k3s.io/quick-start) that includes a default Traefik ingress and local storage provisioner.

Check that

```
kubectl get nodes
```

works.

You must also [install Helm](https://helm.sh/docs/intro/install/).

If you like living on the edge run `curl -sfL https://get.k3s.io | sh -s - --write-kubeconfig-mode=0644` and `curl https://raw.githubusercontent.com/helm/helm/master/scripts/get-helm-3 | bash`

Your host system must support mounting NFS (the executable `mount.nfs` should exist):

```
sudo apt update -y -q
sudo apt install -y -q nfs-common
```

### Mandatory configuration

You must change the ingress hosts before deploying.

Do a global search and replace in all files to replace `penguin.example.org` with your hostname:

- `guacamole.yaml`
- `guacamolehandler.yaml`
- `jupyterhub.yaml`

If you only have an IP use `ip1.ip2.ip3.ip4.nip.io`, e.g. `sed -i -re "s/penguin.example.org/ip1.ip2.ip3.ip4.nip.io/" *.yaml`.

## Optional configuration

If you are using the default K3s setup you _should_ be able to skip this section go straight to the Helm Deployment section.

### Internal DNS server

A CoreDNS deployment independent of the cluster DNS is run in the same namespace as the user pods to prevent DNS leakage.
Since the IP of this DNS server must be used to be configure the pods you should hard-code it.

It is currently set to `10.43.0.11`, corresponding to near the start of the default K3s service CIDR.
If necessary do a global search and replace in all files, changing `10.43.0.11` to whatever your chosen DNS clusterIP is.

- `coredns.yaml`
- `jupyterhub.yaml`

### Default namespace

Currently this assumes everything is installed into the `default` namespace.
If you change this you will need to modify `namespaces default` in `coredns.yaml`.

If you want to install different components in different namespaces everything will break without updating network hostnames.

### MicroK8s

To use [MicroK8s](https://microk8s.io/docs/getting-started) the `hostpath-storage` and `ingress` addons must be installed.
You must modify the `service.clusterIP` in `coredns.yaml` since the MicroK8s CIDR is different.

## Helm Deployment

This assumes everything is done in the `default` namespace, and that the default Traefik ingress setup by K3s is running.

Deploy an NFS server. This will provide shared storage for user pods.
NFS is needed so that multiple services such as the airlock can access the same storage.

```
helm upgrade --install nfs --repo=https://kubernetes-sigs.github.io/nfs-ganesha-server-and-external-provisioner/ nfs-server-provisioner -f nfs-ganesha.yaml --wait
```

Deploy a local CoreDNS server just for user pods.

```
helm upgrade --install coredns-restricted --repo=https://coredns.github.io/helm/ coredns -f coredns.yaml --wait
```

Edit and create shared secret tokens:

```
kubectl apply -f secrets.yaml
```

Deploy Apache Guacamole to provide the virtual desktop interface to user pods.

```
helm upgrade --install --repo=https://www.manicstreetpreacher.co.uk/helm-guacamole/ guacamole guacamole -f guacamole.yaml --wait
```

Deploy JupyterHub

```
helm upgrade --install jupyterhub --repo=https://hub.jupyter.org/helm-chart/ jupyterhub -f jupyterhub.yaml --set-file hub.extraConfig.10-notatre=jupyterhub_extraconfig.py --wait
```

Deploy the JupyterHub Guacamole handler which allows JupyterHub to create Guacamole VDI sessions

```
helm upgrade --install --repo=https://www.manicstreetpreacher.co.uk/helm-generic-webservice/ guacamolehandler generic-webservice -f guacamolehandler.yaml --wait
```

Create an NFS volumes for user home, project, and user egress directories using the NFS provisioner. Edit [`filesystem-directories-pvc.yaml`](filesystem-directories-pvc.yaml) to increase the storage quotas.

```
kubectl apply -f filesystem-directories-pvc.yaml
```

Deploy JupyterHub Airlock which provides a basic interface to requested outputs

```
helm upgrade --install --repo=https://www.manicstreetpreacher.co.uk/helm-generic-webservice/ airlock generic-webservice -f airlock.yaml --wait
```

## Login

If this is working you should be able to go to `http://ingress-hostname/jupyter/`.
Four accounts are setup, no passwords are required (just enter the username and hit `<ENTER>`):

- `admin`: A JupyterHub administrator
- `egress`: An egress (airlock) administrator
- `user-1`: A normal user
- `user-2`: A normal user

Login as `user-1`, start a server in your chosen project.
Follow the links to connect to Guacamole.

You should have a full Ubuntu MATE desktop.
For example, double click on the JupyterLab icon to launch JupyterLab in a browser on the desktop.
Create a file in the `~/egress` folder, either through JupyterLab, or in a terminal: `echo hello > ~/egress/hello.txt`.

Now go to `http://ingress-hostname/jupyter/services/airlock/`.
Click on `New egress`, select the file(s) to egress, and submit.

Go back to `http://ingress-hostname/jupyter/` and logout.

Login as user `egress` and go to `http://ingress-hostname/jupyter/services/airlock/`.
You should see all egresses, and you can click on an egress to accept or reject it.
If you accept it should should be able to log back in as `user-1` and be able to download it.

## Limitations

This is very much a work in progress!

- [ ] Airlock/egress interface is extremely basic
- [ ] Airlock/egress doesn't have a separate API
- [ ] Airlock/egress doesn't have a database, it just uses the presence of files
- [ ] Has not been tested for security!
- [ ] K3s network policies are not complete, should probably replace with Calico
- [ ] Workspaces connections are protected by network rules, not passwords
- [ ] A user can only run one workspace in one project at a time
- [ ] Helm chart and containers versions are not pinned
