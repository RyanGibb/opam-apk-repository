import os
import tarfile

script_dir = os.path.dirname(os.path.abspath(__file__))
cache_dir = os.path.join(script_dir, '../cached')
versions_file = os.path.join(cache_dir, 'versions.txt')
base_dir = 'packages'
os.makedirs(base_dir, exist_ok=True)

def parse_provides_entry(entry):
    if '=' in entry:
        name, version = entry.split('=', 1)
        return name.strip(), version.strip()
    else:
        name = entry
        version = None
        return name.strip(), version

def sanitize_package_name(name):
    return name.replace("/", "-").replace(":", "-").replace(".", "-")

def convert_dep_to_opam(dep, version=None):
    if '>=' in dep:
        pkg, ver = dep.split('>=')
        return f'"{sanitize_package_name(pkg).strip()}" {{>= "{ver.strip()}"}}'
    elif '<=' in dep:
        pkg, ver = dep.split('<=')
        return f'"{sanitize_package_name(pkg).strip()}" {{<= "{ver.strip()}"}}'
    elif '>' in dep:
        pkg, ver = dep.split('>')
        return f'"{sanitize_package_name(pkg).strip()}" {{> "{ver.strip()}"}}'
    elif '<' in dep:
        pkg, ver = dep.split('<')
        return f'"{sanitize_package_name(pkg).strip()}" {{< "{ver.strip()}"}}'
    elif '=' in dep:
        pkg, ver = dep.split('=')
        return f'"{sanitize_package_name(pkg).strip()}" {{= "{ver.strip()}"}}'
    elif '~' in dep:
        pkg, ver = dep.split('~')
        return f'"{sanitize_package_name(pkg).strip()}" {{>= "{ver.strip()}"}}'
    else:
        if version == None:
            return f'"{sanitize_package_name(dep).strip()}"'
        else:
            return f'"{sanitize_package_name(dep).strip()}" {{= "{version}"}}'

def handle_conflicts(dep):
    return f'"{dep[1:].strip()}"'

def process_index(alpine_version):
    apkindex_path = os.path.join(cache_dir, f"{alpine_version}-APKINDEX.tar.gz")
    repo_url = f"https://dl-cdn.alpinelinux.org/alpine/{alpine_version}/main/x86_64/"
    with tarfile.open(apkindex_path, 'r:gz') as index_tar:
        index_file = index_tar.extractfile('APKINDEX')
        if index_file:
            index_content = index_file.read().decode()
        else:
            print(f"error reading {apkindex_path}")
            exit(1)

    pkg = None
    # if two versions of alpine provide the same package version, we will use the later one
    packages = {}
    for line in index_content.splitlines():
        if line.startswith('P:'):
            pkg = line[2:].strip()
            packages[pkg] = {}
            packages[pkg]["version"] = None
            packages[pkg]["dependencies"] = []
            packages[pkg]["provides"] = []
        if line.startswith('V:') and pkg:
            packages[pkg]["version"] = line[2:].strip()
        elif line.startswith('D:') and pkg:
            dependencies = line[2:].strip().split()
            packages[pkg]["dependencies"] = dependencies
        elif line.startswith('p:') and pkg:
            provides = line[2:].strip().split()
            packages[pkg]["provides"] = [parse_provides_entry(provide) for provide in provides]

    virtual_packages = {}
    for package in packages.keys():
        for provide_name, provide_version in packages[package]["provides"]:
            if not provide_name in packages:
              if provide_name in virtual_packages:
                  virtual_packages[provide_name]["dependencies"].append(package)
              else:
                  virtual_packages[provide_name] = {}
                  virtual_packages[provide_name]["dependencies"] = [package]
              #virtual_packages[provide_name]["version"] = provide_version
              # unique per-alpine version
              virtual_packages[provide_name]["version"] = alpine_version[1:]

    for pkg in packages.keys():
        version = packages[pkg]["version"]

        apk_name = f"{pkg}-{version}"
        apk_url = os.path.join(repo_url, f"{apk_name}.apk")
        deps = packages[pkg]["dependencies"]

        package_depends = []
        package_conflicts = []

        for dep in deps:
            if dep.startswith('!'):
                package_conflicts.append(handle_conflicts(dep))
            else:
                dep_name = dep.split('=')[0].split('>=')[0].split('<=')[0].split('<')[0].split('>')[0].split('~')[0]
                if dep_name in packages:
                    package_depends.append(convert_dep_to_opam(dep))
                elif dep_name in virtual_packages:
                    package_depends.append(convert_dep_to_opam(dep))
                else:
                    print(f"Couldn't find dep {dep} for package {apk_name}")

        package_depends = sorted(set(package_depends))
        package_conflicts = sorted(set(package_conflicts))
        formatted_depends = '\n  '.join(package_depends) if package_depends else ''
        formatted_conflicts = '\n  '.join(package_conflicts) if package_conflicts else ''
        opam_depends = f'\ndepends: [\n  {formatted_depends}\n]' if formatted_depends else ''
        opam_conflicts = f'\nconflicts: [\n  {formatted_conflicts}\n]' if formatted_conflicts else ''
        opam_template = """opam-version: "2.0"
build: [
  ["sh" "-c" "sudo apk add {apk_name}.apk"]
]
remove: [
  ["sh" "-c" "sudo apk del {pkg}"]
]{depends}{conflicts}
extra-source "{apk_name}.apk" {{
  src: "{apk_url}"
}}
"""
        opam_content = opam_template.format(
            apk_name=apk_name,
            pkg=pkg,
            apk_url=apk_url,
            depends=opam_depends,
            conflicts=opam_conflicts
        )

        pkg_name = sanitize_package_name(pkg)
        opam_dir = os.path.join(base_dir, pkg_name, f"{pkg_name}.{version}")
        os.makedirs(opam_dir, exist_ok=True)
        opam_file_path = os.path.join(opam_dir, 'opam')
        with open(opam_file_path, 'w') as opam_file:
            opam_file.write(opam_content)

    for pkg in virtual_packages.keys():
        version = virtual_packages[pkg]["version"]
        deps = virtual_packages[pkg]["dependencies"]

        package_depends = []
        if len(deps) == 1:
            dep = deps[0]
            ver = packages[dep]["version"]
            package_depends.append(f'"{sanitize_package_name(dep)}" {{= "{ver}"}}')
        else:
            dep_versions = [(dep, packages[dep]["version"]) for dep in deps]
            joined = ' | '.join(f'"{sanitize_package_name(dep)}" {{= "{ver}"}}' for dep, ver in dep_versions)
            package_depends.append(f"({joined})")

        package_depends = sorted(set(package_depends))
        formatted_depends = '\n  '.join(package_depends) if package_depends else ''
        opam_depends = f'depends: [\n  {formatted_depends}\n]' if formatted_depends else ''
        opam_template = """opam-version: "2.0"
{depends}
"""
        opam_content = opam_template.format(
            depends=opam_depends,
        )

        pkg_name = sanitize_package_name(pkg)
        opam_dir = os.path.join(base_dir, pkg_name, f"{pkg_name}.{version}")
        os.makedirs(opam_dir, exist_ok=True)

        opam_file_path = os.path.join(opam_dir, 'opam')
        with open(opam_file_path, 'w') as opam_file:
            opam_file.write(opam_content)

    print(f"Generated Opam files for alpine version {alpine_version}")

with open(versions_file, 'r') as vf:
    for version in vf:
        version = version.strip()
        print(version)
        process_index(version)
