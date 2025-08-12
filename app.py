from flask import Flask, render_template, request, jsonify
import requests
from dotenv import load_dotenv
import os
import json
import logging
import re

# Pour enregistrer les logs
logging.basicConfig(level=logging.INFO, filename='chatbot.log', format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv()

app = Flask(__name__)

# Configuration de l'API DeepInfra
DEEPINFRA_API_KEY = os.getenv("DEEPINFRA_API_KEY", "STJFoRewRfEn595asO3gqdwtEh7QwEl7")
DEEPINFRA_API_URL = "https://api.deepinfra.com/v1/openai/chat/completions"

# Chargement de la base de connaissances depuis JSON
def load_knowledge_base():
    try:
        with open('knowledge_base.json', 'r', encoding='utf-8') as file:
            data = json.load(file)
            text = []
            for category in data['categories']:
                text.append(f"# {category['name']}\n{category['description']}")
                for item in category['details']:
                    if category['name'] == "Tarification":
                        text.append(f"- {item['range_eur']}: {item['commission']}")
                    elif category['name'] in ["Partenariat", "Commande", "Processus d'Achat"]:
                        text.append(f"{item['step_number']}. {item['description']}")
                    else:
                        text.append(f"- {item['description']}")
                if 'page_target' in category:
                    text.append(f"Plus d’infos disponible sur la page {category['page_target']}")
            return "\n".join(text)
    except FileNotFoundError:
        logging.error("knowledge_base.json not found")
        return "Error: knowledge_base.json not found."
    except Exception as e:
        logging.error(f"Error loading knowledge base: {str(e)}")
        return f"Error loading knowledge base: {str(e)}"

KNOWLEDGE_BASE = load_knowledge_base()

def get_ai_response(user_message):
    headers = {
        "Authorization": f"Bearer {DEEPINFRA_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "meta-llama/Llama-2-70b-chat-hf",
        "messages": [
            {
                "role": "system",
                "content": f"""
                Tu es DaboBot, assistant pour Dabo Academy, dédié à la culture Adinkra et à l’éducation.
                Base de connaissances :
                {KNOWLEDGE_BASE}
                
                Règles :
                - Réponds en français aux questions sur Dabo Academy (produits, contact, commande, activités, etc.).
                - Fournis des réponses très concises, en points, avec le minimum de mots.
                - Liste toutes les étapes ou éléments sans omettre d’info.
                - NE JAMAIS inclure de liens, Markdown ([text](url)), ou HTML (<a href...>).
                - Pour les informations supplémentaires, mentionne la page cible (par exemple, 'Produits', 'Contact', 'Commande') avec : 'Plus d’infos disponible sur la page [NomPage]'.
                - Si info absente, réponds : "Info non disponible. Consultez le site Dabo Academy."
                - Questions hors sujet : "Je réponds uniquement sur Dabo Academy."
                """
            },
            {
                "role": "user",
                "content": user_message
            }
        ],
        "temperature": 0.7,
        "max_tokens": 500
    }
    
    try:
        response = requests.post(DEEPINFRA_API_URL, headers=headers, json=payload)
        response_data = response.json()
        logging.info(f"API response: {response_data}")
        # Nettoyage de tout HTML ou Markdown inattendu dans la réponse
        response_text = response_data['choices'][0]['message']['content']
        response_text = re.sub(r'<[^>]+>', '', response_text) 
        response_text = re.sub(r'&[a-zA-Z0-9#]+;', '', response_text)  
        response_text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1', response_text)  
        return {"choices": [{"message": {"content": response_text}}]}
    except Exception as e:
        logging.error(f"API request failed: {str(e)}")
        raise

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_message = data['message'].strip()
    
    if not user_message:
        return jsonify({"response": "Veuillez entrer une question valide.", "error": True})
    
    try:
        ai_response = get_ai_response(user_message)
        response_text = ai_response['choices'][0]['message']['content']
        return jsonify({"response": response_text, "error": False})
    except Exception as e:
        logging.error(f"Chat error: {str(e)}")
        # Réponse locale par défaut
        fallback_responses = {
            "produits": "Produits : Les sapientogrammes (15€), Adinkra book (15€), Set coloriage (3€), Ballons (4€), Systèmes dynamiques (70€). Plus d’infos disponible sur la page Produits",
            "contact": "Contact : Consultez le site Dabo Academy pour les coordonnées. Plus d’infos disponible sur la page Contact",
            "commande": "Commande : 1. Choisir produit. 2. Ajouter au panier. 3. Payer via site. Plus d’infos disponible sur la page Commande",
            "activités": "Activités : Coloriage Adinkra, collage, apprentissage sapientogrammes, mécatronique. Plus d’infos disponible sur la page Activités"
        }
        
        for keyword, response in fallback_responses.items():
            if keyword.lower() in user_message.lower():
                return jsonify({"response": response, "error": False})
        
        return jsonify({
            "response": "Info non disponible. Consultez le site Dabo Academy.",
            "error": True
        })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5005)