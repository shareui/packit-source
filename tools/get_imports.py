import ast
import os
import sys
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib

def get_pysrc_dir():
    cruel_toml = Path("cruel.toml")
    if cruel_toml.is_file():
        try:
            with open(cruel_toml, "rb") as f:
                data = tomllib.load(f)
            pysrc = data.get("project", {}).get("pysrc")
            if pysrc:
                return Path(pysrc)
        except Exception as e:
            print(f"Warning: could not parse cruel.toml: {e}")
            
    fallbacks = [Path("packit/src/python"), Path("src"), Path(".")]
    for path in fallbacks:
        if path.is_dir(): return path
            
    return Path(".")

def extract_imports_from_file(filepath):
    imports = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content, filename=str(filepath))
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.append(ast.unparse(node))
            elif isinstance(node, ast.ImportFrom):
                imports.append(ast.unparse(node))
                
    except SyntaxError as e:
        print(f"Syntax error in {filepath}: {e}")
    except Exception as e:
        print(f"Failed to process {filepath}: {e}")
        
    return imports

def main():
    pysrc_dir = get_pysrc_dir()
    print(f"Scanning for python files in: {pysrc_dir}")
    
    if not pysrc_dir.exists():
        print(f"Directory {pysrc_dir} does not exist.")
        sys.exit(1)
        
    all_imports = []
    
    for filepath in pysrc_dir.rglob("*.py"):
        all_imports.extend(extract_imports_from_file(filepath))

    unique_imports = list(dict.fromkeys(all_imports))
    
    result_dir = Path("tools/result")
    result_dir.mkdir(parents=True, exist_ok=True)
    
    imports_file = result_dir / "imports.py"
    unique_imports_file = result_dir / "unique_imports.py"
    
    with open(imports_file, "w", encoding="utf-8") as f:
        f.write("# Automatically generated file containing all imports\n\n")
        f.write("\n".join(all_imports))
        f.write("\n")
        
    with open(unique_imports_file, "w", encoding="utf-8") as f:
        f.write("# Automatically generated file containing unique imports\n\n")
        f.write("\n".join(unique_imports))
        f.write("\n")
        
    print(f"Found {len(all_imports)} total imports.")
    print(f"Found {len(unique_imports)} unique imports.")
    print(f"Results saved to {imports_file} and {unique_imports_file}")

if __name__ == "__main__":
    main()
