import pkg_resources as pkr

# List of compatible firmware builds
compat_fw = [511]

# List of compatible patches
compat_patch = [1]

# List of compatible packs
compat_packs = [('python-pymoku', '48A13392DD2B5D81A1F9487934D3411F3C72E1A2'),]

# Compatible network protocol version
protocol_version = '8'

# Official release name
release = pkr.get_distribution("pymoku").version
