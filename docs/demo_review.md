# Journal des corrections — revue humaine de la démo

Le LLM propose, l'humain valide : voici les corrections apportées aux propositions du modèle pour la démo.

Les deux erreurs de classification AI Act ci-dessous sont arrivées avec des justifications légales qui semblaient plausibles à première lecture (citant l'annexe III et l'article 50), mais qui reposaient sur une mauvaise lecture du champ d'application de ces textes. C'est exactement le type d'erreur qu'une revue humaine doit attraper avant qu'un client ne voie le rapport.

| Processus | Cas d'usage | Champ | Valeur du LLM | Valeur corrigée | Raison |
|---|---|---|---|---|---|
| Lettres de relance et appels de recouvrement | Classifieur de priorité de relance | `ai_act` | `high` | `minimal` | Débiteurs = entreprises clientes : l'annexe III (point 5) vise la solvabilité des personnes physiques ; prioriser des relances ne conditionne l'accès à aucun crédit. |
| Lettres de relance et appels de recouvrement | Générateur de lettres de relance | `ai_act` | `limited` | `minimal` | Courriers relus par un humain avant envoi : hors du champ de l'article 50 (chatbots, deepfakes, textes publiés pour informer le public). |
| Préparation et emballage des commandes | Optimisation de la liste de prélèvement | `type` | `generation` | `assistant` | L'outil propose un ordre de prélèvement optimisé à un humain, il ne génère pas de contenu. |

Chaque cas d'usage corrigé porte en plus une entrée `revue_humaine` dans `criteria_rationale`, reprenant cette même explication, pour que la correction reste visible directement dans les données (table des critères de l'application, annexe du rapport PDF).

Fichiers concernés :
- `data/demo_cache/use_cases_fr.json` : sortie brute du LLM (v4.3, claude-haiku-4-5), non modifiée.
- `data/demo_cache/use_cases_fr_reviewed.json` : même contenu, avec les 3 corrections ci-dessus. C'est ce fichier que l'application et les exports de démo utilisent.
