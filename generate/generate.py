import os
import tarfile

script_dir = os.path.dirname(os.path.abspath(__file__))
cache_dir = os.path.join(script_dir, '../cached')
versions_file = os.path.join(cache_dir, 'versions.txt')
base_dir = 'packages'

def parse_provides_entry(entry):
    if '=' in entry:
        name, version = entry.split('=', 1)
        return name.strip(), version.strip()
    else:
        name = entry
        version = None
        return name.strip(), version

def convert_dep_to_opam(dep):
    if '>=' in dep:
        pkg, ver = dep.split('>=')
        return f'"{pkg.strip()}" {{>= "{ver.strip()}"}}'
    elif '<=' in dep:
        pkg, ver = dep.split('<=')
        return f'"{pkg.strip()}" {{<= "{ver.strip()}"}}'
    elif '>' in dep:
        pkg, ver = dep.split('>')
        return f'"{pkg.strip()}" {{> "{ver.strip()}"}}'
    elif '<' in dep:
        pkg, ver = dep.split('<')
        return f'"{pkg.strip()}" {{< "{ver.strip()}"}}'
    elif '=' in dep:
        pkg, ver = dep.split('=')
        return f'"{pkg.strip()}" {{= "{ver.strip()}"}}'
    elif '~' in dep:
        pkg, ver = dep.split('~')
        return f'"{pkg.strip()}" {{>= "{ver.strip()}"}}'
    else:
        return f'"{dep.strip()}"'

def handle_conflicts(dep):
    return f'"{dep[1:].strip()}"'

def generate_opam_files(alpine_version):
    apkindex_path = os.path.join(cache_dir, f"{alpine_version}-APKINDEX.tar.gz")
    repo_url = f"https://dl-cdn.alpinelinux.org/alpine/{alpine_version}/main/x86_64/"
    with tarfile.open(apkindex_path, 'r:gz') as index_tar:
        index_file = index_tar.extractfile('APKINDEX')
        index_content = index_file.read().decode()

    os.makedirs(base_dir, exist_ok=True)

    opam_template = """opam-version: "2.0"
build: [
  ["sh" "-c" "sudo apk add {apk_name}.apk"]
]
remove: [
  ["sh" "-c" "sudo apk del {pkg_name}"]
]{depends}{conflicts}
extra-source "{apk_name}.apk" {{
  src: "{apk_url}"
}}
"""


    package_dependencies = {}
    package_versions = {}
    package_provides = {}
    current_package = None

    for line in index_content.splitlines():
        if line.startswith('P:'):
            current_package = line[2:].strip()
            package_dependencies[current_package] = []
        if line.startswith('V:'):
            current_package_version = line[2:].strip()
            package_versions[current_package] = current_package_version
        elif line.startswith('D:') and current_package:
            dependencies = line[2:].strip().split()
            package_dependencies[current_package] = dependencies
        elif line.startswith('p:') and current_package:
            provides = line[2:].strip().split()
            for provide in provides:
                provide_name, provide_version = parse_provides_entry(provide)
                # TODO do we need to take provide_version into account?
                if provide_name not in package_provides:
                    package_provides[provide_name] = []
                package_provides[provide_name].append(current_package)

    for pkg_name in package_dependencies.keys():
        version = package_versions[pkg_name]
        apk_name = f"{pkg_name}-{version}"
        apk_url = os.path.join(repo_url, f"{apk_name}.apk")
        depends = package_dependencies.get(pkg_name, [])

        package_depends = []
        package_conflicts = []

        for dep_version in depends:
            if dep_version.startswith('!'):
                package_conflicts.append(handle_conflicts(dep_version))
            else:
                dep = dep_version.split('=')[0].split('>=')[0].split('<=')[0].split('<')[0].split('>')[0].split('~')[0]
                if dep in package_provides:
                    # TODO what if we have a so version?
                    providers = package_provides[dep]
                    if len(providers) == 1:
                        package_depends.append(convert_dep_to_opam(providers[0]))
                    else:
                        package_depends.append(f"({' | '.join(convert_dep_to_opam(p) for p in providers)})")
                elif dep in package_dependencies:
                    package_depends.append(convert_dep_to_opam(dep_version))
                else:
                    print(f"Couldn't find dep {dep} for package {apk_name}")

        package_depends = sorted(set(package_depends))
        package_conflicts = sorted(set(package_conflicts))
        formatted_depends = '\n  '.join(package_depends) if package_depends else ''
        formatted_conflicts = '\n  '.join(package_conflicts) if package_conflicts else ''

        opam_depends = f'\ndepends: [\n  {formatted_depends}\n]' if formatted_depends else ''
        opam_conflicts = f'\nconflicts: [\n  {formatted_conflicts}\n]' if formatted_conflicts else ''

        opam_content = opam_template.format(
            apk_name=apk_name,
            pkg_name=pkg_name,
            apk_url=apk_url,
            depends=opam_depends,
            conflicts=opam_conflicts
        )

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
        generate_opam_files(version)
