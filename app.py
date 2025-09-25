from flask import Flask, render_template, request, jsonify
import pandas as pd
import os

app = Flask(__name__)

def load_bacteria_data():
    """Charge les données des bactéries depuis le fichier Excel"""
    excel_path = os.path.join('data', 'Bacterie_sensibilite.xlsx')
    df = pd.read_excel(excel_path, sheet_name='DATA')
    return df

def get_bacteria_by_type(df, type_filter=None):
    """Retourne les bactéries filtrées par type (bacterie/resistance) ou toutes si None"""
    if type_filter is None:
        return df.iloc[:, 0].dropna().tolist()

    filtered_df = df[df['type'] == type_filter]
    return filtered_df.iloc[:, 0].dropna().tolist()

def check_bgn_exception(selected_items, exam_direct, df):
    """Vérifie les exceptions BGN et retourne le traitement approprié"""
    if 'BGN' not in exam_direct:
        return None

    # Vérifier s'il n'y a pas de bactéries BGN sélectionnées
    bgn_bacteria = []
    for item in selected_items:
        item_row = df[df.iloc[:, 0] == item]
        if not item_row.empty:
            is_bgn = item_row.get('is_bgn')
            if is_bgn is not None and not is_bgn.empty:
                if is_bgn.iloc[0] == True or str(is_bgn.iloc[0]).lower() == 'true':
                    bgn_bacteria.append(item)

    # Si aucune bactérie BGN sélectionnée, appliquer les exceptions
    if not bgn_bacteria:
        # Vérifier les bactéries atypiques
        atypical_bacteria = ['Chlamydia pneumoniae', 'Legionella pneumophila', 'Mycoplasma pneumoniae']
        has_atypical = any(bacteria in selected_items for bacteria in atypical_bacteria)

        if has_atypical and 'MRSA' in selected_items:
            return 'Cefepime + Amikacine + Spiramycine + Linezolide'

        if has_atypical:
            return 'Cefepime + Amikacine + Spiramycine'

        # Vérifier MRSA
        if 'MRSA' in selected_items:
            return 'Cefepime + Amikacine + Linezolide'

        # Cas par défaut
        return 'Cefepime + Amikacine'

    return None

def find_best_common_treatment_without_exceptions(bacteria_list, df):
    """Trouve le meilleur traitement commun pour les bactéries sélectionnées (logique de base)"""
    if not bacteria_list:
        return None

    # Filtrer les données pour les bactéries sélectionnées
    bacteria_data = df[df.iloc[:, 0].isin(bacteria_list)]

    if bacteria_data.empty:
        return None

    # Colonnes des traitements (à partir de la colonne D, index 3, car colonne C est maintenant 'type')
    treatment_columns = df.columns[3:]

    best_treatment = None
    best_score = float('inf')

    for col in treatment_columns:
        # Vérifier si toutes les bactéries ont un traitement dans cette colonne
        treatment_scores = []
        valid_for_all = True

        for bacteria in bacteria_list:
            bacteria_row = bacteria_data[bacteria_data.iloc[:, 0] == bacteria]
            if not bacteria_row.empty:
                score = bacteria_row[col].iloc[0]
                if pd.isna(score) or score == '':
                    valid_for_all = False
                    break
                try:
                    score_int = int(score)
                    treatment_scores.append(score_int)
                except:
                    valid_for_all = False
                    break

        if valid_for_all and treatment_scores:
            # Le meilleur traitement commun est celui avec la somme des scores la plus faible
            total_score = sum(treatment_scores)
            if total_score < best_score:
                best_score = total_score
                best_treatment = col

    return best_treatment

def handle_no_common_treatment_exceptions(bacteria_list, df):
    """Gère les exceptions quand aucun traitement commun n'est trouvé"""
    atypical_bacteria = ['Chlamydia pneumoniae', 'Legionella pneumophila', 'Mycoplasma pneumoniae']

    additional_treatments = []
    remaining_bacteria = bacteria_list.copy()

    # Étape 1: Traiter les bactéries atypiques
    has_atypical = [bacteria for bacteria in remaining_bacteria if bacteria in atypical_bacteria]
    if has_atypical:
        additional_treatments.append('Spiramycine')
        remaining_bacteria = [b for b in remaining_bacteria if b not in atypical_bacteria]

        # Essayer de trouver un traitement avec les bactéries restantes
        base_treatment = find_best_common_treatment_without_exceptions(remaining_bacteria, df)
        if base_treatment:
            return f"{base_treatment} + {' + '.join(additional_treatments)}"

    # Étape 2: Traiter MRSA (si toujours pas de traitement)
    has_mrsa = 'MRSA' in remaining_bacteria
    if has_mrsa:
        additional_treatments.append('Linezolide')
        remaining_bacteria = [b for b in remaining_bacteria if b not in ['MRSA', 'Staphylococcus aureus']]

        # Essayer de trouver un traitement avec les bactéries restantes
        base_treatment = find_best_common_treatment_without_exceptions(remaining_bacteria, df)
        if base_treatment:
            return f"{base_treatment} + {' + '.join(additional_treatments)}"

    # Étape 3: Traiter SA seul (si toujours pas de traitement)
    has_sa = 'Staphylococcus aureus' in remaining_bacteria
    if has_sa:
        additional_treatments.append('Oracilline (ou Cefazoline si récurrence)')
        remaining_bacteria = [b for b in remaining_bacteria if b != 'Staphylococcus aureus']

        # Essayer de trouver un traitement avec les bactéries restantes
        base_treatment = find_best_common_treatment_without_exceptions(remaining_bacteria, df)
        if base_treatment:
            return f"{base_treatment} + {' + '.join(additional_treatments)}"

    # Si on a des traitements additionnels mais pas de traitement de base
    if additional_treatments:
        return ' + '.join(additional_treatments)

    # Si aucune exception ne s'applique ou ne résout le problème
    return None

def find_best_common_treatment(bacteria_list, df, exam_direct=None):
    """Trouve le meilleur traitement commun pour les bactéries sélectionnées"""
    if not bacteria_list:
        return None

    # Vérifier les exceptions BGN en premier
    if exam_direct:
        bgn_exception = check_bgn_exception(bacteria_list, exam_direct, df)
        if bgn_exception:
            return bgn_exception

    # Essayer de trouver un traitement commun classique
    best_treatment = find_best_common_treatment_without_exceptions(bacteria_list, df)

    # Si aucun traitement commun trouvé, appliquer les exceptions
    if not best_treatment:
        return handle_no_common_treatment_exceptions(bacteria_list, df)

    return best_treatment

@app.route('/')
def index():
    try:
        df = load_bacteria_data()
        bacteria_list = get_bacteria_by_type(df, 'bacterie')
        resistance_list = get_bacteria_by_type(df, 'resistance')
        all_items = df.iloc[:, 0].dropna().tolist()

        return render_template('index.html',
                             bacteria_list=bacteria_list,
                             resistance_list=resistance_list,
                             all_items=all_items)
    except Exception as e:
        return f"Erreur lors du chargement des données: {str(e)}"

@app.route('/find_treatment', methods=['POST'])
def find_treatment():
    try:
        data = request.get_json()
        selected_items = data.get('bacteria', [])
        exam_direct_results = data.get('examDirect', [])

        if not selected_items:
            return jsonify({'error': 'Aucun élément sélectionné'})

        df = load_bacteria_data()
        best_treatment = find_best_common_treatment(selected_items, df, exam_direct_results)

        if best_treatment:
            # Séparer les bactéries et les résistances
            bacteria_list = []
            resistance_list = []

            for item in selected_items:
                item_row = df[df.iloc[:, 0] == item]
                if not item_row.empty:
                    item_type = item_row['type'].iloc[0]
                    if item_type == 'bacterie':
                        bacteria_list.append(item)
                    elif item_type == 'resistance':
                        resistance_list.append(item)

            return jsonify({
                'success': True,
                'treatment': best_treatment,
                'bacteria': bacteria_list,
                'resistances': resistance_list
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Aucun traitement commun trouvé pour ces éléments'
            })

    except Exception as e:
        return jsonify({'error': f'Erreur: {str(e)}'})

if __name__ == '__main__':
    app.run(debug=True)