import os
import tarfile
from bs4 import BeautifulSoup

script_dir = os.path.dirname(os.path.abspath(__file__))

repo_url = 'https://dl-cdn.alpinelinux.org/alpine/v3.20/main/x86_64/'
base_dir = 'packages'
apkindex_local_path = os.path.join(script_dir, 'APKINDEX.tar.gz')
index_html_local_path = os.path.join(script_dir, 'index.html')

with open(index_html_local_path, 'r') as f:
    index_html_content = f.read()

soup = BeautifulSoup(index_html_content, 'html.parser')
apk_links = [a['href'] for a in soup.find_all('a') if a['href'].endswith('.apk')]

opam_template = """opam-version: "2.0"
build: [
  ["sh" "-c" "sudo apk add {apk_name}"]
]
remove: [
  ["sh" "-c" "sudo apk del {pkg_name}"]
]
{depends}
{conflicts}
extra-source "{apk_name}" {{
  src: "{apk_url}"
}}
"""

def parse_apk_name(apk_name):
    parts = apk_name[:-4].rsplit('-', 2)
    pkg_name = parts[0]
    version = '-'.join(parts[1:])
    return pkg_name, version

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

with tarfile.open(apkindex_local_path, 'r:gz') as index_tar:
    index_file = index_tar.extractfile('APKINDEX')
    index_content = index_file.read().decode()

package_dependencies = {}
package_provides = {}
current_package = None

for line in index_content.splitlines():
    if line.startswith('P:'):
        current_package = line[2:].strip()
        package_dependencies[current_package] = []
    elif line.startswith('D:') and current_package:
        dependencies = line[2:].strip().split()
        package_dependencies[current_package] = dependencies
    elif line.startswith('p:') and current_package:
        provides = line[2:].strip().split()
        for provide in provides:
            provide_name = provide.split('=')[0]
            if provide_name not in package_provides:
                package_provides[provide_name] = []
            package_provides[provide_name].append(current_package)

for apk_link in apk_links:
    apk_name = apk_link
    pkg_name, version = parse_apk_name(apk_name)
    apk_url = os.path.join(repo_url, apk_link)
    depends = package_dependencies.get(pkg_name, [])

    package_depends = []
    package_conflicts = []

    for dep_version in depends:
        if dep_version.startswith('!'):
            package_conflicts.append(handle_conflicts(dep_version))
        else:
            dep = dep_version.split('=')[0].split('>=')[0].split('<=')[0].split('<')[0].split('>')[0].split('~')[0]
            if dep in package_provides:
                providers = package_provides[dep]
                if len(providers) == 1:
                    package_depends.append(convert_dep_to_opam(providers[0]))
                else:
                    package_depends.append(f"({' | '.join(convert_dep_to_opam(p) for p in providers)})")
            elif dep in package_dependencies:
                package_depends.append(convert_dep_to_opam(dep))
            else:
                print(f"Couldn't find dep {dep} for package {apk_name}")

    package_depends = sorted(set(package_depends))
    package_conflicts = sorted(set(package_conflicts))
    formatted_depends = '\n  '.join(package_depends) if package_depends else ''
    formatted_conflicts = '\n  '.join(package_conflicts) if package_conflicts else ''

    opam_depends = f'depends: [\n  {formatted_depends}\n]' if formatted_depends else ''
    opam_conflicts = f'conflicts: [\n  {formatted_conflicts}\n]' if formatted_conflicts else ''

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

print(f"Generated {len(apk_links)} Opam files in {base_dir}")
