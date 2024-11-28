import os

def define_env(env):
    """
    Define the custom macro for reading a file.
    """
    @env.macro
    def read_file(filepath):
        # Resolve the file path relative to the mkdocs.yml file
        full_path = os.path.join(env.project_dir, filepath)
        try:
            with open(full_path, 'r') as file:
                return file.read()
        except FileNotFoundError:
            return f"Error: File {filepath} not found."
