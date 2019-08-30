import pkg_resources as pkr

# List of compatible firmware builds
compat_fw = [511]

# List of compatible patches
compat_patch = [0]

# List of compatible packs
compat_packs = []

# Compatible network protocol version
protocol_version = '8'

# Official release name
release = pkr.get_distribution("pymoku").version
