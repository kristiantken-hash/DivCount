from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class UserInfo:
    nome: str
    cpf: Optional[str] = None


@dataclass
class ExpenseManagerConfig:
    users: Dict[str, UserInfo] = field(default_factory=dict)
    categories: Dict[str, List[str]] = field(default_factory=dict)


class ExpenseManager:
    """
    Regras de negócio básicas:
    - Identificação de pagador a partir de CPF.
    - Sugestão de categoria com base em palavras-chave.
    """

    def __init__(self, config: Optional[ExpenseManagerConfig] = None) -> None:
        if config is None:
            config = self._default_config()
        self.config = config

    def _default_config(self) -> ExpenseManagerConfig:
        """
        Configuração padrão de usuários e categorias.
        Aqui ficam apenas os 'palpites' iniciais; o app pode aprender depois
        via tabela memoria_itens no banco.
        """
        users = {
            "Kristian": UserInfo(nome="Kristian", cpf="018.491.380-28"),
            "Giulia": UserInfo(nome="Giulia", cpf="000.000.000-00"),
        }

        categories = {
            "Hortifruti": [
                "PESSEGO", "MANGA", "LIMAO", "MELAO", "ALFACE", "BROCOLIS",
                "FRUTA", "LEGUME", "BANANA", "MACA", "UVA", "BATATA",
                "CEBOLA", "TOMATE", "CENOURA", "ABACATE", "MAMAO", "LARANJA",
                "COUVE", "REPOLHO", "ABOBORA", "ALHO", "PIMENTAO",
            ],
            "Carnes": [
                "FILEZIN", "SASSAMI", "FRANGO", "CARNE", "BOI", "RES",
                "PEITO", "COXA", "SOBRECOXA", "MOIDA", "PATINHO", "ALCATRA",
                "BIFE", "LINGUICA", "SALSICHA", "PRESUNTO", "CALABRESA",
            ],
            "Bebidas": [
                "AGUA", "SUCO", "REFRIGERANTE", "CERVEJA", "VIO",
                "COCA", "PEPSI", "FANTA", "SPRITE", "GUARANA", "VINHO",
                "VODKA", "ENERGETICO", "CHA", "CAFE", "LEITE",
            ],
            "Padaria": [
                "PANETTONE", "PAO", "BOLO", "TORRADA", "BISCOITO",
                "BOLACHA", "SALGADINHO", "CROISSANT", "QUEIJO", "REQUEIJAO",
                "MANTEIGA", "MARGARINA", "IOGURTE",
            ],
            "Limpeza": [
                "DETERGENTE", "SABAO", "ALVEJANTE", "PAPEL", "AMACIANTE",
                "DESINFETANTE", "ESPONJA", "LIXO", "ALCOOL", "MULTI USO",
                "SANITARIA", "AZULIM", "YPÊ", "OMO",
            ],
            "Higiene": [
                "SHAMPOO", "CONDICIONADOR", "SABONETE", "PASTA", "CREME",
                "DESODORANTE", "FIO DENTAL", "ESCOVA", "COTTONETE",
            ],
        }

        return ExpenseManagerConfig(users=users, categories=categories)

    # -------------------------
    # Identificação de pagador
    # -------------------------
    def identify_payer(self, cpf_found: Optional[str]) -> str:
        """
        Recebe um CPF e tenta mapear para um usuário conhecido.
        Retorna "Outro" ou "Desconhecido (Sem CPF)" quando não encontra.
        """
        if not cpf_found:
            return "Desconhecido (Sem CPF)"

        for name, user in self.config.users.items():
            if user.cpf and user.cpf == cpf_found:
                return name

        return "Outro"

    # -------------------------
    # Sugestão de categoria
    # -------------------------
    def categorize_item(self, item_name: str) -> str:
        """
        Sugere uma categoria apenas com base em palavras-chave do nome do item.
        Esta função é o 'palpite padrão'; no fluxo principal do app,
        você pode primeiro consultar a memória (database.get_learned_category)
        e usar este método só como fallback.
        """
        if not item_name:
            return "Geral"

        item_upper = item_name.upper()

        for category, keywords in self.config.categories.items():
            for keyword in keywords:
                if keyword in item_upper:
                    return category

        return "Geral"
