# Gvisor

https://gist.github.com/Frichetten/c77ee24b12edd2ab852738fc8221a1f1

```sh
curl -fsSL https://gvisor.dev/archive.key | sudo gpg --dearmor -o /usr/share/keyrings/gvisor-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/gvisor-archive-keyring.gpg] https://storage.googleapis.com/gvisor/releases release main" | sudo tee /etc/apt/sources.list.d/gvisor.list > /dev/null

sudo apt-get update && sudo apt-get install -y runsc

sudo cp gvisor/config.toml.tmpl /var/lib/rancher/k3s/agent/etc/containerd/config.toml.tmpl
sudo cp gvisor/runsc.toml /etc/containerd/runsc.toml

sudo systemctl daemon-reload
sudo systemctl restart k3s

kubectl apply -f gvisor/runtimeclass.yaml

helm upgrade --install jupyterhub --repo=https://hub.jupyter.org/helm-chart/ jupyterhub -f jupyterhub.yaml -f gvisor/jupyterhub.yaml --wait
```
