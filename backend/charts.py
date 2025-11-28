import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from io import BytesIO
import re

def parse_value(text):
    """
    Extracts the first numeric value from a string.
    Returns 0.0 if no number is found.
    """
    if not text or not isinstance(text, str):
        return 0.0
    match = re.search(r"([\d\.]+)", text)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return 0.0
    return 0.0

def create_bar_chart(data, title, ylabel, color='#2c3e50'):
    """
    Creates a professional bar chart and returns it as a BytesIO object.
    data: List of tuples (label, value)
    """
    labels = [item[0] for item in data]
    values = [item[1] for item in data]

    plt.figure(figsize=(10, 6)) # Larger figure
    
    # Professional style
    plt.rcParams['font.family'] = 'sans-serif'
    plt.rcParams['font.sans-serif'] = ['Arial', 'Helvetica', 'DejaVu Sans']
    
    bars = plt.bar(labels, values, color=color, edgecolor='black', alpha=0.8, width=0.6, zorder=3)
    
    plt.title(title, fontsize=16, fontweight='bold', pad=20, color='#333333')
    plt.ylabel(ylabel, fontsize=12, fontweight='bold', labelpad=10)
    plt.xlabel("Materials", fontsize=12, fontweight='bold', labelpad=10)
    
    # Grid
    plt.grid(axis='y', linestyle='--', alpha=0.5, zorder=0)
    
    plt.xticks(rotation=0, ha='center', fontsize=10)
    plt.yticks(fontsize=10)
    
    # Add value labels on top of bars
    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height + (max(values)*0.01),
                f'{height:.1f}',
                ha='center', va='bottom', fontsize=10, fontweight='bold')

    # Add margins
    plt.margins(y=0.1)
    plt.tight_layout()
    
    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=300, bbox_inches='tight')
    plt.close()
    buffer.seek(0)
    return buffer

def create_radar_chart(materials, attributes):
    """
    Creates a professional radar chart comparing multiple materials.
    materials: List of dicts {'name': str, 'values': [float]}
    attributes: List of attribute names corresponding to values
    """
    # Number of variables
    N = len(attributes)
    
    # Compute angle for each axis
    angles = [n / float(N) * 2 * np.pi for n in range(N)]
    angles += angles[:1] # Close the loop
    
    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))
    
    # Draw one axe per variable + add labels
    plt.xticks(angles[:-1], attributes, size=11, fontweight='bold')
    
    # Draw ylabels
    ax.set_rlabel_position(0)
    plt.yticks([20, 40, 60, 80, 100], ["20", "40", "60", "80", "100"], color="grey", size=9)
    plt.ylim(0, 100)
    
    # Plot each material
    colors = ['#e74c3c', '#3498db', '#2ecc71', '#9b59b6', '#f1c40f']
    linestyles = ['-', '--', '-.', ':', '-']
    
    for i, material in enumerate(materials):
        values = material['values']
        values += values[:1] # Close the loop
        
        color = colors[i % len(colors)]
        linestyle = linestyles[i % len(linestyles)]
        
        ax.plot(angles, values, linewidth=2, linestyle=linestyle, label=material['name'], color=color)
        ax.fill(angles, values, color=color, alpha=0.1)
    
    plt.title('Material Performance Comparison', size=18, fontweight='bold', y=1.1, color='#333333')
    
    # Legend
    plt.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1), fontsize=10, frameon=True, shadow=True)
    
    plt.tight_layout()
    
    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=300, bbox_inches='tight')
    plt.close()
    buffer.seek(0)
    return buffer

def generate_charts(report_data):
    """
    Generates all charts based on report data.
    Returns a dictionary of chart_type -> BytesIO
    """
    matches = report_data.get("matches", [])
    if not matches:
        return {}

    charts = {}
    
    # 1. Tensile Strength
    tensile_data = []
    for m in matches:
        props = m.get("properties", {})
        val = 0
        for k, v in props.items():
            if "tensile" in k.lower() or "strength" in k.lower():
                val = parse_value(v)
                break
        tensile_data.append((m.get("name", "Unknown"), val))
    
    if any(d[1] > 0 for d in tensile_data):
        charts['tensile'] = create_bar_chart(tensile_data, "Tensile Strength Comparison", "Strength (MPa)", color='#34495e')

    # 2. Density
    density_data = []
    for m in matches:
        props = m.get("properties", {})
        val = 0
        for k, v in props.items():
            if "density" in k.lower():
                val = parse_value(v)
                break
        density_data.append((m.get("name", "Unknown"), val))
        
    if any(d[1] > 0 for d in density_data):
        charts['density'] = create_bar_chart(density_data, "Density Comparison", "Density (g/cm³)", color='#e67e22')

    # 3. Radar Chart
    radar_materials = []
    attributes = ["Strength", "Density", "Cost", "Corrosion", "Temp"]
    
    # Helper to normalize a list of values to 0-100 scale
    def normalize(vals, inverse=False):
        max_v = max(vals) if vals else 1
        if max_v == 0: max_v = 1
        if inverse:
            return [(1 - (v / max_v)) * 100 for v in vals]
        return [(v / max_v) * 100 for v in vals]

    # Extract raw values for all materials first
    raw_data = {attr: [] for attr in attributes}
    
    for m in matches:
        props = m.get("properties", {})
        
        # Strength
        s_val = 0
        for k, v in props.items():
            if "tensile" in k.lower() or "strength" in k.lower(): s_val = parse_value(v); break
        raw_data["Strength"].append(s_val)
        
        # Density
        d_val = 0
        for k, v in props.items():
            if "density" in k.lower(): d_val = parse_value(v); break
        raw_data["Density"].append(d_val)
        
        # Cost (inverse)
        c_val = 0
        for k, v in props.items():
            if "cost" in k.lower(): c_val = parse_value(v); break
        raw_data["Cost"].append(c_val) 
        
        # Corrosion (qualitative -> quantitative mapping)
        cor_val = 50 # Default
        for k, v in props.items():
            if "corrosion" in k.lower():
                v_lower = v.lower()
                if "excellent" in v_lower: cor_val = 95
                elif "good" in v_lower: cor_val = 75
                elif "fair" in v_lower: cor_val = 50
                elif "poor" in v_lower: cor_val = 25
                break
        raw_data["Corrosion"].append(cor_val)
        
        # Temp
        t_val = 0
        for k, v in props.items():
            if "temp" in k.lower() or "melting" in k.lower(): t_val = parse_value(v); break
        raw_data["Temp"].append(t_val)

    # Normalize
    norm_data = {}
    norm_data["Strength"] = normalize(raw_data["Strength"])
    norm_data["Density"] = normalize(raw_data["Density"], inverse=True) 
    norm_data["Cost"] = normalize(raw_data["Cost"], inverse=True) 
    norm_data["Corrosion"] = raw_data["Corrosion"] 
    norm_data["Temp"] = normalize(raw_data["Temp"])

    # Reconstruct per material
    for i, m in enumerate(matches):
        values = [
            norm_data["Strength"][i],
            norm_data["Density"][i], 
            norm_data["Cost"][i],
            norm_data["Corrosion"][i],
            norm_data["Temp"][i]
        ]
        radar_materials.append({'name': m.get("name", "Unknown"), 'values': values})

    if radar_materials:
        charts['radar'] = create_radar_chart(radar_materials, attributes)

    return charts
