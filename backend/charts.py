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

def create_bar_chart(data, title, ylabel, color='skyblue'):
    """
    Creates a bar chart and returns it as a BytesIO object.
    data: List of tuples (label, value)
    """
    labels = [item[0] for item in data]
    values = [item[1] for item in data]

    plt.figure(figsize=(8, 5))
    bars = plt.bar(labels, values, color=color, edgecolor='black', alpha=0.7)
    
    plt.title(title, fontsize=14, fontweight='bold', pad=15)
    plt.ylabel(ylabel, fontsize=12)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.xticks(rotation=45, ha='right')
    
    # Add value labels on top of bars
    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.1f}',
                ha='center', va='bottom')

    plt.tight_layout()
    
    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=100)
    plt.close()
    buffer.seek(0)
    return buffer

def create_radar_chart(materials, attributes):
    """
    Creates a radar chart comparing multiple materials.
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
    plt.xticks(angles[:-1], attributes)
    
    # Draw ylabels
    ax.set_rlabel_position(0)
    plt.yticks([20, 40, 60, 80, 100], ["20", "40", "60", "80", "100"], color="grey", size=7)
    plt.ylim(0, 100)
    
    # Plot each material
    colors = ['b', 'r', 'g', 'm', 'y']
    for i, material in enumerate(materials):
        values = material['values']
        values += values[:1] # Close the loop
        ax.plot(angles, values, linewidth=1, linestyle='solid', label=material['name'], color=colors[i % len(colors)])
        ax.fill(angles, values, color=colors[i % len(colors)], alpha=0.1)
    
    plt.title('Material Performance Comparison', size=15, y=1.1)
    plt.legend(loc='upper right', bbox_to_anchor=(0.1, 0.1))
    
    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=100)
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
        # Look for keys like "Tensile Strength", "Strength", etc.
        val = 0
        for k, v in props.items():
            if "tensile" in k.lower() or "strength" in k.lower():
                val = parse_value(v)
                break
        tensile_data.append((m.get("name", "Unknown"), val))
    
    if any(d[1] > 0 for d in tensile_data):
        charts['tensile'] = create_bar_chart(tensile_data, "Tensile Strength Comparison", "Strength (MPa)", color='#4e79a7')

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
        charts['density'] = create_bar_chart(density_data, "Density Comparison", "Density (g/cm³)", color='#f28e2b')

    # 3. Radar Chart (Normalized values approx)
    # This is tricky without real normalized data. We'll try to extract 0-100 scores if available, 
    # or normalize the raw values we found relative to the max in the set.
    
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
        raw_data["Cost"].append(c_val) # Will invert later
        
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
    norm_data["Density"] = normalize(raw_data["Density"], inverse=True) # Lower density is usually better? Or just different. Let's assume lower is "lighter" -> 100? 
    # Actually for radar charts "Performance", usually higher is better. So Lightness = 1/Density.
    # Let's just plot normalized values.
    
    norm_data["Cost"] = normalize(raw_data["Cost"], inverse=True) # Lower cost is better
    norm_data["Corrosion"] = raw_data["Corrosion"] # Already 0-100
    norm_data["Temp"] = normalize(raw_data["Temp"])

    # Reconstruct per material
    for i, m in enumerate(matches):
        values = [
            norm_data["Strength"][i],
            norm_data["Density"][i], # This is actually "Lightness" if inverted, or just relative density. Let's keep it simple.
            norm_data["Cost"][i],
            norm_data["Corrosion"][i],
            norm_data["Temp"][i]
        ]
        radar_materials.append({'name': m.get("name", "Unknown"), 'values': values})

    if radar_materials:
        charts['radar'] = create_radar_chart(radar_materials, attributes)

    return charts
