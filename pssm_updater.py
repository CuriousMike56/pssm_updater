import os
import re
import argparse
from pathlib import Path

class PSSMMaterialUpdater:
    def __init__(self, input_folder):
        self.input_folder = Path(input_folder)
        self.backup_folder = self.input_folder / "old_materials"
        self.backup_folder.mkdir(exist_ok=True)
        self.processed_files = 0
        self.processed_materials = 0
        self.updated_materials = 0

    def parse_material_file(self, content):
        # Split file into individual material definitions
        materials = re.split(r'material\s+', content)[1:]  # Skip empty first element
        return [f"material {mat}" for mat in materials]

    def is_eligible_material(self, material_text):
        # Reject if material contains shaders or tex_coord_set
        if any(x in material_text for x in ['vertex_program_ref', 'fragment_program_ref', 'tex_coord_set']):
            return False

        # Count blocks
        pass_count = len(re.findall(r'\bpass\s*{', material_text))
        texture_unit_count = len(re.findall(r'\btexture_unit\s*{', material_text))

        # Accept materials with:
        # - 1 or 2 passes
        # - Exactly 1 texture_unit
        return (pass_count in [1, 2]) and texture_unit_count == 1

    def transform_material(self, material_text):
        # Extract material name while preserving any whitespace after it
        name_match = re.match(r'material\s+([^\n{]+)([\s]*)', material_text)
        material_name = name_match.group(1).strip()
        name_whitespace = name_match.group(2)
        
        # Find the content between the outer braces while preserving whitespace
        start_brace = material_text.find('{')
        end_brace = material_text.rfind('}')
        pre_brace_ws = material_text[len(f"material {material_name}"):start_brace]
        inner_content = material_text[start_brace+1:end_brace]
        
        # Transform technique name
        inner_content = re.sub(r'\btechnique\b(?=\s*{)', 'technique BaseTechnique', inner_content)
        
        # Find all pass blocks and only rename the one containing texture_unit
        def replace_pass(match):
            pass_block = match.group(0)
            if 'texture_unit' in pass_block:
                return pass_block.replace('pass', 'pass BaseRender', 1)
            return pass_block
            
        inner_content = re.sub(r'pass\s*{[^}]*}', replace_pass, inner_content, flags=re.DOTALL)
        
        # Transform texture_unit
        inner_content = re.sub(r'\btexture_unit\b(?=\s*{)', 'texture_unit Diffuse_Map', inner_content)
        
        # Reconstruct with original formatting
        return f"material {material_name}: RoR/Managed_Mats/Base{pre_brace_ws}{{{inner_content}}}"

    def process_file(self, file_path):
        print(f"Processing {file_path.name}...")
        with open(file_path, 'r') as f:
            content = f.read()

        materials = self.parse_material_file(content)
        updated_materials = []
        updated_count = 0
        
        for material in materials:
            self.processed_materials += 1
            if self.is_eligible_material(material):
                updated_materials.append(self.transform_material(material))
                updated_count += 1
                self.updated_materials += 1
            else:
                updated_materials.append(material)

        # Only update file if we actually changed something
        if updated_count > 0:
            # Create backup
            backup_path = self.backup_folder / file_path.name
            import shutil
            shutil.copy2(file_path, backup_path)
            
            # Write updated content to original file
            output_content = 'import * from "managed_mats.material"\n\n' + '\n\n'.join(updated_materials)
            with open(file_path, 'w') as f:
                f.write(output_content)
            print(f"  updated {updated_count} materials, original backed up to {self.backup_folder}\{backup_path.name}")
            self.processed_files += 1
        else:
            print("  No eligible materials found")

    def run(self):
        print(f"Scanning folder: {self.input_folder}")
        print(f"Backup folder: {self.backup_folder}")
        
        material_files = list(self.input_folder.glob('*.material'))
        if not material_files:
            print("No .material files found!")
            return

        for file_path in material_files:
            self.process_file(file_path)

        print("\nSummary:")
        print(f"Files processed: {self.processed_files}")
        print(f"Materials found: {self.processed_materials}")
        print(f"Materials updated with shadows support: {self.updated_materials}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Update materials wih PSSM shadows support')
    parser.add_argument('input_folder', help='Path to the folder containing material files')
    args = parser.parse_args()

    updater = PSSMMaterialUpdater(args.input_folder)
    updater.run()
