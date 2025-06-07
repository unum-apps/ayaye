k8s_yaml(kustomize('kubernetes/tilt'))

k8s_resource(
  objects=['ayaye:namespace'],
  new_name='namespace'
)

local_resource(
    name='config', resource_deps=['namespace'],
    cmd='kubectx docker-desktop && kubectl -n ayaye create configmap config --from-file config/ --dry-run=client -o yaml | kubectl apply -f -'
)

local_resource(
    name='secret', resource_deps=['namespace'],
    cmd='kubectx docker-desktop && kubectl -n ayaye create secret generic secret --from-file secret/ --dry-run=client -o yaml | kubectl apply -f -'
)

# daemon

docker_build('ayaye-daemon', './daemon')
k8s_resource('daemon', port_forwards=['23333:5678'])
