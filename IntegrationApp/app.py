import streamlit as st
import pandas as pd
import networkx as nx
from pyvis.network import Network
import tempfile
import os

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Data Integration APP Map", 
    layout="wide", 
    page_icon="🕸️"
)

# --- DATA PERSISTENCE FUNCTIONS ---
FILES = {
    "groups": "data_groups.csv",
    "systems": "data_systems.csv",
    "owners": "data_owners.csv",
    "integrations": "data_integrations.csv"
}

def load_data(key):
    if not os.path.exists(FILES[key]):
        if key == "groups": return pd.DataFrame(columns=["Group Name", "Description"])
        if key == "systems": return pd.DataFrame(columns=["System Name", "Description", "Group", "Color"])
        if key == "owners": return pd.DataFrame(columns=["Name", "Email", "Role"])
        if key == "integrations": return pd.DataFrame(columns=["ID", "Integration Name", "Description", "Source System", "Source Conn", "Target System", "Target Conn", "Business Owner", "IT Owner"])
        return pd.DataFrame()
    
    df = pd.read_csv(FILES[key])
    if key == "integrations" and "Description" not in df.columns:
        df["Description"] = ""
    return df

def save_data(key, df):
    df.to_csv(FILES[key], index=False)

# --- INITIALIZE STATE ---
for key in FILES.keys():
    if key not in st.session_state:
        st.session_state[key] = load_data(key)

# --- CONSTANTS ---
CONNECTION_TYPES = [
    "API", "Database", "Lakehouse", "Report", 
    "Event Streams", "CSV File", "Manual Integration", "Web Services"
]
DEFAULT_COLOR = "#D3D3D3"

# ==========================================
# SIDEBAR & FULLSCREEN LOGIC
# ==========================================
with st.sidebar:
    try:
        st.image("bctransitlogo.png", use_container_width=True) 
    except Exception:
        st.write("📂 Logo not found")
        
    st.divider()
    st.header("App Controls")
    
    fullscreen_mode = st.toggle("🖥️ Fullscreen Visualization Mode", value=False)
    
    st.info("Toggle this on to hide data entry tabs and expand the network view.")

# ==========================================
# MAIN HEADER
# ==========================================
if not fullscreen_mode:
    st.title("Data Integration APP Map")
    st.markdown("Map your system landscape, integrations, and dependencies.")
    st.divider()

# ==========================================
# HELPER: GENERATE NETWORK HTML
# ==========================================
def generate_network_html(df_sys, df_int, layout_style, view_mode, focus_node, selected_group, height_px):
    
    G = nx.MultiDiGraph() # Grafo Multi-Direcionado
    
    # 1. Add Nodes
    for _, row in df_sys.iterrows():
        if selected_group and row['Group'] not in selected_group:
            continue
        
        tooltip = f"<b>{row['System Name']}</b><br>Group: {row['Group']}<br>{row['Description']}"
        
        raw_color = row['Color']
        final_color = DEFAULT_COLOR
        if pd.notna(raw_color) and str(raw_color).strip() != "":
                final_color = raw_color
        
        G.add_node(
            row['System Name'], 
            label=row['System Name'], 
            title=tooltip, 
            color=final_color, 
            group=row['Group'], 
            shape="dot", 
            size=25,
            font={'size': 16, 'color': 'white'} # Fonte definida no nó
        )

    # --- TRACKER PARA CURVATURA ---
    edge_tracker = {} 

    # 2. Add Edges
    for _, row in df_int.iterrows():
        if row['Source System'] in G.nodes and row['Target System'] in G.nodes:
            
            # Identifica par único (Origem -> Destino)
            pair_key = (row['Source System'], row['Target System'])
            idx = edge_tracker.get(pair_key, 0)
            edge_tracker[pair_key] = idx + 1
            
            # --- CÁLCULO DE CURVATURA (ZIG-ZAG ROBUSTO) ---
            # Para garantir que linhas não se sobreponham, alternamos lados e aumentamos o arco.
            
            # Se for a 1ª linha (idx 0): Curvatura 0.2
            # Se for a 2ª linha (idx 1): Curvatura -0.2
            # Se for a 3ª linha (idx 2): Curvatura 0.4
            # Se for a 4ª linha (idx 3): Curvatura -0.4
            
            base_curve = 0.2
            step = 0.15 # Passo maior para visibilidade
            
            direction = 1 if idx % 2 == 0 else -1
            magnitude = base_curve + ((idx // 2) * step)
            roundness_val = magnitude * direction

            connection_label = f"{row['Source Conn']} / {row['Target Conn']}"
            
            edge_tooltip = f"""
            <b>{row['Integration Name']}</b><br>
            {row['Description']}<br>
            <hr>
            Type: {row['Source Conn']} ➔ {row['Target Conn']}<br>
            Biz Owner: {row['Business Owner']}<br>
            IT Owner: {row['IT Owner']}
            """
            
            # AQUI: Definimos TUDO sobre a aresta localmente para evitar override global
            G.add_edge(
                row['Source System'], 
                row['Target System'], 
                title=edge_tooltip, 
                label=connection_label,
                color={'inherit': 'from'},
                font={'size': 10, 'color': 'white', 'strokeWidth': 2, 'strokeColor': '#222222', 'align': 'middle'},
                smooth={'type': 'curvedCW', 'roundness': roundness_val}, # Força Curvatura Manual
                arrows={'to': {'enabled': True, 'scaleFactor': 1}}
            )

    # 3. Focus Logic
    if view_mode == "Focus System (Lineage)" and focus_node:
        if focus_node in G:
            upstream = list(G.predecessors(focus_node))
            downstream = list(G.successors(focus_node))
            nodes_to_keep = set([focus_node] + upstream + downstream)
            G = G.subgraph(list(nodes_to_keep))

    # 4. Generate PyVis
    if len(G.nodes) > 0:
        net = Network(height=f'{height_px}px', width='100%', bgcolor='#222222', font_color='white', directed=True)
        net.from_nx(G)
        
        # --- OPTIONS LOGIC (SEM BLOCO DE EDGES GLOBAL) ---
        # Removemos a configuração global de 'edges' e 'smooth' para respeitar a configuração individual acima.
        
        if layout_style == "Hierarchical (Bottom-Up)":
            options_script = """
            var options = {
              "layout": {
                "hierarchical": {
                  "enabled": true,
                  "direction": "DU",
                  "sortMethod": "directed",
                  "nodeSpacing": 350,
                  "levelSeparation": 300,
                  "blockShifting": true,
                  "edgeMinimization": false
                }
              },
              "physics": {
                "enabled": false
              },
              "nodes": { 
                "borderWidth": 2, 
                "shadow": true
              }
            }
            """
        else:
            # Organic
            options_script = """
            var options = {
              "nodes": { 
                "borderWidth": 2,
                "shadow": true
              },
              "physics": { 
                "barnesHut": { 
                    "gravitationalConstant": -3000, 
                    "centralGravity": 0.3, 
                    "springLength": 300, 
                    "springConstant": 0.001, 
                    "damping": 0.5,
                    "avoidOverlap": 0.2
                }, 
                "minVelocity": 0.75 
              }
            }
            """

        net.set_options(options_script)
        
        try:
            path = os.path.join(tempfile.gettempdir(), "network_v13.html")
            net.save_graph(path)
            with open(path, 'r', encoding='utf-8') as f: 
                return f.read()
        except Exception as e: 
            return f"Error: {e}"
    else:
        return None

# ==========================================
# HELPER: RENDER UI
# ==========================================
def render_visualizer_ui(height_px):
    df_sys = st.session_state['systems']
    df_int = st.session_state['integrations']
    
    if df_int.empty:
        st.info("No integrations to display.")
        return

    c_filter1, c_filter2 = st.columns([1, 4])
    
    with c_filter1:
        st.markdown("### 🔍 Controls")
        layout_style = st.radio("Layout Style", ["Organic (Neural)", "Hierarchical (Bottom-Up)"])
        view_mode = st.radio("View Mode", ["Full Network", "Focus System (Lineage)"])
        selected_group = st.multiselect("Filter by Group", df_sys['Group'].unique())
        
        focus_node = None
        if view_mode == "Focus System (Lineage)":
            focus_node = st.selectbox("Select System to Focus", df_sys['System Name'].unique())

    with c_filter2:
        html_data = generate_network_html(
            df_sys, df_int, 
            layout_style, view_mode, focus_node, selected_group, 
            height_px 
        )
        
        if html_data:
            st.components.v1.html(html_data, height=height_px + 10)
        else:
            st.warning("No data matches filters.")

# ==========================================
# MAIN LOGIC FLOW
# ==========================================

if fullscreen_mode:
    st.header("🖥️ Fullscreen Analysis Mode")
    render_visualizer_ui(height_px=950) 
else:
    tab_groups, tab_owners, tab_systems, tab_integrations, tab_visual = st.tabs([
        "1. Groups (Edit)", "2. Owners (Edit)", "3. Systems (Edit)", "4. Integrations (Search & Edit)", "5. Network Visualization"
    ])

    # ---------------------------------
    # TAB 1: GROUPS
    # ---------------------------------
    with tab_groups:
        st.header("System Groups Management")
        col_add, col_edit = st.columns([1, 2])
        
        with col_add:
            st.subheader("Add New Group")
            with st.form("group_form"):
                g_name = st.text_input("Group Name")
                g_desc = st.text_area("Description")
                submitted = st.form_submit_button("Add")
                if submitted and g_name:
                    if g_name in st.session_state['groups']['Group Name'].values:
                        st.error("Group exists.")
                    else:
                        new_row = pd.DataFrame([{"Group Name": g_name, "Description": g_desc}])
                        st.session_state['groups'] = pd.concat([st.session_state['groups'], new_row], ignore_index=True)
                        save_data("groups", st.session_state['groups'])
                        st.success("Added!")
                        st.rerun()

        with col_edit:
            st.subheader("Edit Existing Groups")
            edited_groups = st.data_editor(st.session_state['groups'], num_rows="dynamic", use_container_width=True, key="edit_groups_table")
            if st.button("💾 Save Groups Changes"):
                st.session_state['groups'] = edited_groups
                save_data("groups", st.session_state['groups'])
                st.success("Groups updated!")

    # ---------------------------------
    # TAB 2: OWNERS
    # ---------------------------------
    with tab_owners:
        st.header("Stakeholder Registry")
        col_add, col_edit = st.columns([1, 2])
        
        with col_add:
            st.subheader("Add New Owner")
            with st.form("owner_form"):
                o_name = st.text_input("Name")
                o_email = st.text_input("Email")
                o_role = st.selectbox("Role", ["Business Owner", "IT Owner"])
                submitted = st.form_submit_button("Add")
                if submitted and o_name:
                    new_row = pd.DataFrame([{"Name": o_name, "Email": o_email, "Role": o_role}])
                    st.session_state['owners'] = pd.concat([st.session_state['owners'], new_row], ignore_index=True)
                    save_data("owners", st.session_state['owners'])
                    st.success("Owner added!")
                    st.rerun()

        with col_edit:
            st.subheader("Edit Owners")
            column_config_owners = {"Role": st.column_config.SelectboxColumn(options=["Business Owner", "IT Owner"])}
            edited_owners = st.data_editor(st.session_state['owners'], column_config=column_config_owners, num_rows="dynamic", use_container_width=True, key="edit_owners_table")
            if st.button("💾 Save Owners Changes"):
                st.session_state['owners'] = edited_owners
                save_data("owners", st.session_state['owners'])
                st.success("Owners updated!")

    # ---------------------------------
    # TAB 3: SYSTEMS
    # ---------------------------------
    with tab_systems:
        st.header("Systems Inventory")
        col_add, col_edit = st.columns([1, 2])
        
        with col_add:
            st.subheader("Add New System")
            if st.session_state['groups'].empty:
                st.warning("Create a Group first.")
            else:
                with st.form("sys_form"):
                    s_name = st.text_input("System Name")
                    s_desc = st.text_area("Description")
                    s_group = st.selectbox("Group", list(st.session_state['groups']['Group Name'].unique()))
                    s_color = st.color_picker("Node Color (Default: Light Gray)", DEFAULT_COLOR)
                    submitted = st.form_submit_button("Register System")
                    if submitted and s_name:
                        if s_name in st.session_state['systems']['System Name'].values:
                            st.error("System exists.")
                        else:
                            new_row = pd.DataFrame([{"System Name": s_name, "Description": s_desc, "Group": s_group, "Color": s_color}])
                            st.session_state['systems'] = pd.concat([st.session_state['systems'], new_row], ignore_index=True)
                            save_data("systems", st.session_state['systems'])
                            st.success("System added!")
                            st.rerun()

        with col_edit:
            st.subheader("Edit Systems")
            if not st.session_state['systems'].empty:
                column_config_sys = {
                    "Group": st.column_config.SelectboxColumn(options=list(st.session_state['groups']['Group Name'].unique())),
                    "Color": st.column_config.TextColumn(label="Node Color (Hex)", help="Example: #FF0000", validate="^#[0-9a-fA-F]{6}$")
                }
                edited_systems = st.data_editor(st.session_state['systems'], column_config=column_config_sys, num_rows="dynamic", use_container_width=True, key="edit_systems_table")
                if st.button("💾 Save Systems Changes"):
                    st.session_state['systems'] = edited_systems
                    save_data("systems", st.session_state['systems'])
                    st.success("Systems updated!")

    # ---------------------------------
    # TAB 4: INTEGRATIONS
    # ---------------------------------
    with tab_integrations:
        st.header("Integration Management")
        system_list = list(st.session_state['systems']['System Name'].unique()) if not st.session_state['systems'].empty else []
        biz_owners = list(st.session_state['owners'][st.session_state['owners']['Role'] == "Business Owner"]['Name'].unique()) if not st.session_state['owners'].empty else []
        it_owners = list(st.session_state['owners'][st.session_state['owners']['Role'] == "IT Owner"]['Name'].unique()) if not st.session_state['owners'].empty else []

        with st.expander("➕ Create New Integration", expanded=False):
            if not system_list:
                st.error("Please register Systems first.")
            else:
                with st.form("int_form_add"):
                    i_name = st.text_input("Integration Name (Unique)")
                    i_desc = st.text_area("Integration Description / Details")
                    c1, c2 = st.columns(2)
                    with c1:
                        src_sys = st.selectbox("Source System", system_list, key="src_s")
                        src_conn = st.selectbox("Source Connection", CONNECTION_TYPES, key="src_c")
                    with c2:
                        tgt_sys = st.selectbox("Target System", system_list, key="tgt_s")
                        tgt_conn = st.selectbox("Target Connection", CONNECTION_TYPES, key="tgt_c")
                    c3, c4 = st.columns(2)
                    bo = c3.selectbox("Business Owner", biz_owners) if biz_owners else c3.text_input("Biz Owner")
                    io = c4.selectbox("IT Owner", it_owners) if it_owners else c4.text_input("IT Owner")
                    submitted = st.form_submit_button("Create Integration")
                    if submitted and i_name:
                        if i_name in st.session_state['integrations']['Integration Name'].values:
                            st.error("Integration Name already exists.")
                        else:
                            new_id = len(st.session_state['integrations']) + 1
                            new_row = pd.DataFrame([{
                                "ID": new_id, "Integration Name": i_name, "Description": i_desc,
                                "Source System": src_sys, "Source Conn": src_conn,
                                "Target System": tgt_sys, "Target Conn": tgt_conn,
                                "Business Owner": bo, "IT Owner": io
                            }])
                            st.session_state['integrations'] = pd.concat([st.session_state['integrations'], new_row], ignore_index=True)
                            save_data("integrations", st.session_state['integrations'])
                            st.success("Integration Created!")
                            st.rerun()
        st.divider()
        st.subheader("🔍 Search & Find")
        search_term = st.text_input("Type to search...", placeholder="e.g., 'API', 'Finance'")
        df_integrations = st.session_state['integrations']
        if search_term:
            mask = df_integrations.astype(str).apply(lambda x: x.str.contains(search_term, case=False)).any(axis=1)
            st.dataframe(df_integrations[mask], use_container_width=True, hide_index=True)
        else:
            st.info("Enter text to search.")
        st.divider()
        st.subheader("📋 Master Integration Editor")
        if not df_integrations.empty:
            column_config = {
                "ID": st.column_config.NumberColumn(disabled=True),
                "Integration Name": st.column_config.TextColumn(required=True),
                "Description": st.column_config.TextColumn(width="large"),
                "Source System": st.column_config.SelectboxColumn(options=system_list, required=True),
                "Target System": st.column_config.SelectboxColumn(options=system_list, required=True),
                "Source Conn": st.column_config.SelectboxColumn(options=CONNECTION_TYPES, required=True),
                "Target Conn": st.column_config.SelectboxColumn(options=CONNECTION_TYPES, required=True),
                "Business Owner": st.column_config.SelectboxColumn(options=biz_owners),
                "IT Owner": st.column_config.SelectboxColumn(options=it_owners)
            }
            edited_df = st.data_editor(df_integrations, column_config=column_config, num_rows="dynamic", use_container_width=True, key="editor_integrations_main")
            if st.button("💾 Save Integration Changes"):
                if len(edited_df['Integration Name']) != len(edited_df['Integration Name'].unique()):
                    st.error("Error: Duplicate Integration Names detected.")
                else:
                    st.session_state['integrations'] = edited_df
                    save_data("integrations", st.session_state['integrations'])
                    st.success("All changes saved!")
                    st.rerun()

    with tab_visual:
        st.header("Network Visualization")
        render_visualizer_ui(height_px=650)