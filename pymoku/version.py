import pkg_resources as pkr

# List of compatible firmware builds
compat_fw = [501]

# List of compatible patches
compat_patch = [1]

# List of compatible packs
compat_packs = [('python-py', '7439434C8782832F134C21090D4E32DB49896171\n')]

# Compatible network protocol version
protocol_version = '7'

# Official release name
release = pkr.get_distribution("pymoku").version
