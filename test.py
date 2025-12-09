import re, requests, json
from typing import Dict, Optional, Any, List
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, AnyMessage
from langgraph.graph import StateGraph, END
from typing_extensions import TypedDict, Annotated
import operator

OFFDATA_KEY = "rsgdRTKp1S53Nc0S"
OPENROUTER_KEY = "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"

model = ChatOpenAI(model="qwen/qwen3-235b-a22b-2507", temperature=0.1, api_key=OPENROUTER_KEY,
                   base_url="https://openrouter.ai/api/v1")


class State(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    context_company: Optional[Dict]
    context_requisites: Optional[Dict]
    context_mode: str


def parse_requisites(text: str) -> Dict[str, Optional[str]]:
    """Извлечение параметров текущего текста"""
    print(f"🔍 Обрабатываем ваш запрос: '{text[:50]}...'")
    numbers = re.findall(r'\b(\d{8,15})\b', text)
    print(f"   Цифры: {numbers}")

    result = {'inn': None, 'ogrn': None, 'kpp': None, 'okpo': None}
    for num in numbers:
        num_len = len(num)
        if num_len in (10, 12):
            result['inn'] = num; print(f"   ✅ ИНН: {num}")
        elif num_len in (13, 15):
            result['ogrn'] = num; print(f"   ✅ ОГРН: {num}")
        elif num_len == 9:
            result['kpp'] = num; print(f"   ✅ КПП: {num}")
        elif num_len in (8, 10):
            result['okpo'] = num; print(f"   ✅ ОКПО: {num}")

    print(f"📋 Результат: {result}")
    return result


def detect_discrepancy(reqs: Dict[str, str], company: Dict) -> List[Dict]:
    discrepancies = []

    checks = [
        ('ogrn', 'ОГРН'), ('inn', 'ИНН'), ('okpo', 'ОКПО')
    ]
    for field, field_name in checks:
        user_val = reqs[field]
        found_val = str(company.get(field.upper(), '')).strip()
        if user_val and found_val and user_val != found_val:
            discrepancies.append({
                'type': field, 'user': user_val, 'found': found_val,
                'company_name': company.get('НаимСокр', 'N/A')
            })

    if reqs.get('inn') and reqs.get('kpp'):
        found_kpp = str(company.get('КПП', '')).strip()
        if reqs['kpp'] != found_kpp and found_kpp:
            discrepancies.append({
                'type': 'kpp', 'user': reqs['kpp'], 'found': found_kpp,
                'company_name': company.get('НаимСокр', 'N/A')
            })

    print(f"🔍 Расхождений: {len(discrepancies)}")
    return discrepancies


def search_ofdata(params: Dict[str, str]) -> Dict[str, Any]:
    """API поиск"""
    search_order = []
    if params.get('okpo'): search_order.append(('okpo', params['okpo']))
    if params.get('ogrn'): search_order.append(('ogrn', params['ogrn']))
    if params.get('inn'):
        search_order.append(('inn', params['inn']))
        if params.get('kpp'): print(f"  💡 ИНН+КПП: {params['inn']}+{params['kpp']}")

    print(f"\n🔍 Поиск: {search_order}")

    for field, value in search_order:
        payload = {"key": OFFDATA_KEY, field: value}
        if field == 'inn' and params.get('kpp'): payload['kpp'] = params['kpp']

        print(f"  📡 POST {field}={value}{' + КПП' if field == 'inn' and params.get('kpp') else ''}")

        try:
            resp = requests.post("https://api.ofdata.ru/v2/company", json=payload, timeout=10,
                                 headers={'Content-Type': 'application/json'})
            data = resp.json()
            if "data" in data and data["data"]:
                company = data["data"]
                print(f"✅ НАЙДЕНО: {company.get('НаимСокр')}")
                return {'success': True, 'company': company, 'found_by': field}
        except Exception as e:
            print(f"❌ Ошибка: {e}")

    return {'success': False, 'message': 'Компания не найдена'}


def format_discrepancy_message(discrepancies: List[Dict], reqs: Dict[str, str], company: Dict) -> str:
    """Расхождения"""
    lines = ["⚠️ РАСХОЖДЕНИЯ РЕКВИЗИТОВ:"]

    type_names = {'inn': 'ИНН', 'ogrn': 'ОГРН', 'kpp': 'КПП', 'okpo': 'ОКПО'}
    for disc in discrepancies:
        type_name = type_names.get(disc['type'], disc['type'].upper())
        lines.append(f"• Ваш {type_name} `{disc['user']}` ≠ `{disc['found']}` ({disc['company_name']})")

    choices = []
    choice_num = 1
    if reqs.get('okpo'):
        choices.append(f"{choice_num}️⃣ ОКПО `{reqs['okpo']}`");
        choice_num += 1
    if reqs.get('ogrn'):
        choices.append(f"{choice_num}️⃣ ОГРН `{reqs['ogrn']}`");
        choice_num += 1
    if reqs.get('inn'):
        inn_kpp = reqs['inn'];
        if reqs.get('kpp'): inn_kpp += f"/{reqs['kpp']}"
        choices.append(f"{choice_num}️⃣ **ИНН{'+КПП' if reqs.get('kpp') else ''}** `{inn_kpp}`");
        choice_num += 1
    choices.append(f"{choice_num}️⃣ Найденная `{company.get('НаимСокр', 'N/A')}`")

    lines.extend(["", "❓ Выберите источник:"] + choices)
    return "\n".join(lines)


def format_company_card(company: Dict) -> str:
    """Карточка компании"""
    status = company.get('Статус', {}).get('Наим', 'N/A')
    return f"""✅ {company.get('НаимПолн', company.get('НаимСокр', 'N/A'))}

    Реквизиты:
    • ИНН: `{company.get('ИНН', 'N/A')}`
    • ОГРН: `{company.get('ОГРН', 'N/A')}`
    • КПП: `{company.get('КПП', 'N/A')}`

    Статус: {status}
    Регион: {company.get('Регион', {}).get('Наим', 'N/A')}
    Адрес: {company.get('ЮрАдрес', {}).get('АдресРФ', 'N/A')}"""


def handle_choice(state: State) -> Dict:
    """Обработка выбора"""
    choice = state['messages'][-1].content.strip().lower()
    company = state['context_company']

    notes = {'1': 'По ОКПО', '2': 'По ОГРН', '3': 'По ИНН'}
    if state['context_requisites'].get('inn') and state['context_requisites'].get('kpp'):
        notes['4'] = 'По ИНН+КПП'

    note = notes.get(choice, "По найденной компании")
    summary = format_company_card(company) + f"\n\n💡 *{note}*"

    return {"messages": [AIMessage(content=summary)], "context_mode": "search"}

def sanctions_risk_check(company: Dict) -> Dict[str, Any]:
    """ПРОВЕРКА САНКЦИЙ — УЧИТЫВАЮТСЯ ТОЛЬКО РОССИЙСКИЕ САНКЦИИ"""
    data = company.get('data', {})

    # 1. БАЗОВЫЕ САНКЦИИ — НО ТОЛЬКО РОССИЙСКИЕ
    direct_sanctions_raw = data.get('Санкции', False)
    founder_sanctions = data.get('СанкцУчр', False)
    sanctions_countries = data.get('СанкцииСтраны', [])

    # Считаем, что "Санкции: true" относится к РФ, ТОЛЬКО если:
    #   в СанкцииСтраны есть Россия
    #   нет других стран
    #   источник явно РФ
    is_rf_sanctions = (
        direct_sanctions_raw
        and (
            "Россия" in sanctions_countries
            or "РОССИЯ" in [c.upper() for c in sanctions_countries]
            or len(sanctions_countries) == 0  # fallback: если стран нет — предполагаем РФ
        )
    )

    # 2. УПРАВЛЯЮЩАЯ ОРГАНИЗАЦИЯ
    upr_org = data.get('УпрОрг', {})
    upr_foreign = bool(upr_org.get('ИнСтрана'))
    upr_nedost = upr_org.get('Недост', False)
    upr_risk = 0.35 if upr_foreign else (0.15 if upr_nedost else 0.0)

    # 3. УЧРЕДИТЕЛИ
    uchred = data.get('Учред', {})
    inorg_count = len(uchred.get('ИнОрг', []))
    rosorg_nedost = any(org.get('Недост', False) for org in uchred.get('РосОрг', []))
    inorg_risk = 0.40 if inorg_count > 0 else 0.0
    rosorg_risk = 0.15 if rosorg_nedost else 0.0

    # 4. ПОДРАЗДЕЛЕНИЯ
    podrazd = data.get('Подразд', {})
    filials = podrazd.get('Филиал', [])
    predstv = podrazd.get('Представ', [])

    foreign_filials = sum(1 for f in filials if f.get('Страна') and f.get('Страна') != 'Россия')
    foreign_predstv = sum(1 for p in predstv if p.get('Страна') and p.get('Страна') != 'Россия')
    foreign_podrazd_risk = 0.30 if (foreign_filials + foreign_predstv) > 0 else 0.0

    restricted_filials = sum(1 for f in filials if not f.get('ОгрДоступ', True))
    restricted_predstv = sum(1 for p in predstv if not p.get('ОгрДоступ', True))
    restricted_risk = 0.10 if (restricted_filials + restricted_predstv) > 0 else 0.0

    # 5. ОБЩИЙ
    risk = (
        0.50 * int(is_rf_sanctions) +
        0.45 * int(founder_sanctions) +
        upr_risk +
        inorg_risk +
        rosorg_risk +
        foreign_podrazd_risk +
        restricted_risk
    )
    total_risk = min(risk, 1.0)

    # 6. УРОВНИ
    if total_risk < 0.2:
        level, status_152fz, rec = "🟢 ЧИСТАЯ", "✅ ОК", "✅ РАБОТАЙТЕ"
    elif total_risk < 0.5:
        level, status_152fz, rec = "🟡 НИЗКИЙ", "🟡 ПРОВЕРИТЬ", "⚠️ ДОП. ПРОВЕРКА"
    elif total_risk < 0.8:
        level, status_152fz, rec = "🟠 СРЕДНИЙ", "❌ РИСК", "⚠️ РУЧНАЯ ПРОВЕРКА"
    else:
        level, status_152fz, rec = "🔴 БЛОКИРОВКА", "🚫 ЗАПРЕЩЕНО", "❌ НЕ РАБОТАЙТЕ"

    # 7. РИСКИ
    risk_factors = []
    if is_rf_sanctions:
        risk_factors.append("🔴 Санкции РФ")
    elif direct_sanctions_raw:
        risk_factors.append("⚠️ Санкции иностранных государств (не РФ)")
    if founder_sanctions:
        risk_factors.append("🔴 Санкции учредителей")
    if upr_foreign:
        risk_factors.append("🌍 УпрОрг иностранная")
    if upr_nedost:
        risk_factors.append("🇷🇺 УпрОрг недостоверная")
    if inorg_count > 0:
        risk_factors.append(f"🌍 Иностранные учредители: {inorg_count}")
    if rosorg_nedost:
        risk_factors.append("🇷🇺 Недостоверные российские учредители")
    if restricted_risk > 0:
        risk_factors.append(f"Ограничения доступа к сведениям от ФНС")
    if foreign_podrazd_risk > 0:
        risk_factors.append(f"Имеет иностранные подзарзделения")


    return {
        'total_risk': round(total_risk, 2),
        'level': level,
        'status_152fz': status_152fz,
        'recommendation': rec,
        'direct_sanctions_rf': is_rf_sanctions,
        'direct_sanctions_any': direct_sanctions_raw,
        'founder_sanctions': founder_sanctions,
        'management': {'foreign': upr_foreign, 'nedost': upr_nedost},
        'founders': {'inorg': inorg_count, 'rosorg_nedost': rosorg_nedost},
        'sanctions_countries': sanctions_countries,
        'risk_factors': risk_factors,
        'safe': total_risk < 0.3
    }


def _safe_sanctions_check(company: Dict) -> Dict:
    """Обёртка для гарантии совместимости структуры."""
    if "data" in company:
        company = company["data"]
    return sanctions_risk_check({"data": company})


def build_final_response(company: Dict, risk_report: Dict) -> str:
    """Генерирует финальную карточку с блоком рисков."""
    base_card = format_company_card(company)

    risk_lines = [
        f"\n\n⚠️ ОЦЕНКА РИСКОВ (152-ФЗ)",
        f"• Уровень: {risk_report['level']}",
        f"• Рекомендация: {risk_report['recommendation']}",
        f"• Скор риска: {risk_report['total_risk']}"
    ]

    if risk_report['risk_factors']:
        risk_lines.append("\n🔍 Факторы риска:")
        risk_lines.extend([f"  - {f}" for f in risk_report['risk_factors']])

    return base_card + "\n".join(risk_lines)


def tool_node(state: State):
    """Главная логика поиска"""
    messages = [msg for msg in state["messages"] if isinstance(msg, HumanMessage)]
    if not messages:
        return {"messages": [AIMessage(content="❌ Нет запроса!")]}

    user_text = messages[-1].content
    reqs = parse_requisites(user_text)

    if state.get('context_mode') == 'choice':
        return handle_choice(state)

    if state.get('context_mode') == 'kpp_only' and reqs.get('inn'):
        full_reqs = {**state['context_requisites'], **reqs}
        api_result = search_ofdata(full_reqs)

        if not api_result['success']:
            return {"messages": [
                AIMessage(content=f"❌ Не найдено по ИНН `{reqs['inn']}` + КПП `{state['context_requisites']['kpp']}`")],
                    "context_mode": "search"}

        company = api_result['company']
        discrepancies = detect_discrepancy(full_reqs, company)
        result = {"context_company": company, "context_requisites": full_reqs}

        if discrepancies:
            result.update({
                "messages": [AIMessage(content=format_discrepancy_message(discrepancies, full_reqs, company))],
                "context_mode": 'choice'
            })
        else:
            risk_report = _safe_sanctions_check(company)
            result["messages"] = [AIMessage(content=build_final_response(company, risk_report))]
        return result

    # Обычный поиск
    if not any(reqs.values()):
        return {"messages": [AIMessage(content="❌ Введите ИНН/ОГРН/ОКПО!\n💡 Пример: '7736050003'")]}

    api_result = search_ofdata(reqs)
    if not api_result['success']:
        return {"messages": [AIMessage(content=f"❌ {api_result['message']}")]}

    company = api_result['company']
    discrepancies = detect_discrepancy(reqs, company)
    result = {"context_company": company, "context_requisites": reqs}

    if discrepancies:
        result.update({
            "messages": [AIMessage(content=format_discrepancy_message(discrepancies, reqs, company))],
            "context_mode": 'choice'
        })
    else:
        risk_report = _safe_sanctions_check(company)
        result["messages"] = [AIMessage(content=build_final_response(company, risk_report))]

    return result


SYSTEM_PROMPT = """Ты ассистент ЕГРЮЛ - эксперт по реквизитам российских компаний.

Твоя задача:
1. Парсить ИНН/ОГРН из запроса пользователя
2. Искать данные через API ofdata.ru  
3. Если есть расхождения реквизитов → спрашивать выбор (1️⃣ ОГРН, 2️⃣ ИНН, 3️⃣ Найденная)
4. Показывать полную карточку компании

Никогда не придумывай данные - только из API!Отвечай только по делу, без лишних слов."""


def agent_node(state: State):
    context_info = f"Режим: {state.get('context_mode', 'search')}"
    if state.get('context_company'):
        context_info += f" | Компания: {state['context_company'].get('НаимСокр', 'нет')}"

    system_msg = AIMessage(content=SYSTEM_PROMPT + f"\n\n{context_info}")
    response = model.invoke([system_msg] + state["messages"][-3:])
    return {"messages": [response]}


def should_continue(state: State):
    """Роутер"""
    last_content = state["messages"][-1].content.lower()
    if state.get('context_mode') == 'choice': return "tool"
    if any(c in last_content for c in ['1', '2', '3', 'огрн', 'инн']) or re.search(r'\b(\d{10,15})\b', last_content):
        return "tool"
    return END


graph = StateGraph(State)
graph.add_node("agent", agent_node)
graph.add_node("tool", tool_node)
graph.set_entry_point("agent")
graph.add_conditional_edges("agent", should_continue, {"tool": "tool", END: END})
graph.add_edge("tool", END)
app = graph.compile()

if __name__ == "__main__":
    print("🤖 ЕГРЮЛ-Ассистент готов!")
    state = {"messages": [], "context_company": None, "context_requisites": None, "context_mode": "search"}

    while True:
        user_input = input("\n📝 Запрос: ").strip()
        if user_input.lower() in ['выход', 'q']: break

        state["messages"].append(HumanMessage(content=user_input))
        result = app.invoke(state.copy())

        state["messages"] = [result["messages"][-1]]
        for k in ["context_company", "context_requisites", "context_mode"]:
            state[k] = result.get(k, state[k])

        print()
        result["messages"][-1].pretty_print()
