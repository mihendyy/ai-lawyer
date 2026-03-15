"""Схема данных для BPMN-стиля диаграммы (дорожки по ответственным)."""

# Формат, который ожидаем от модели:
#
# {
#   "lanes": [
#     { "id": "lane1", "title": "Заказчик" },
#     { "id": "lane2", "title": "Исполнитель" }
#   ],
#   "steps": [
#     { "id": "s1", "laneId": "lane1", "label": "Подписание договора", "type": "start" },
#     { "id": "s2", "laneId": "lane1", "label": "Оплата 50%", "type": "task" },
#     { "id": "s3", "laneId": "lane2", "label": "Выполнение работ", "type": "task" },
#     { "id": "s4", "laneId": "lane2", "label": "Завершено?", "type": "decision" },
#     { "id": "s5", "laneId": "lane1", "label": "Приёмка", "type": "end" }
#   ],
#   "connections": [
#     { "from": "s1", "to": "s2" },
#     { "from": "s2", "to": "s3" },
#     { "from": "s3", "to": "s4" },
#     { "from": "s4", "to": "s5", "label": "Да" },
#     { "from": "s4", "to": "s3", "label": "Нет" }
#   ]
# }
#
# type шага: "start" | "task" | "decision" | "end"

def validate_bpmn_data(data: dict) -> bool:
    """Проверяет минимальную валидность структуры."""
    if not isinstance(data, dict):
        return False
    lanes = data.get("lanes")
    steps = data.get("steps")
    connections = data.get("connections")
    if not isinstance(lanes, list) or not isinstance(steps, list) or not isinstance(connections, list):
        return False
    if not lanes or not steps:
        return False
    lane_ids = {l.get("id") for l in lanes if isinstance(l, dict) and l.get("id")}
    step_ids = {s.get("id") for s in steps if isinstance(s, dict) and s.get("id")}
    if not lane_ids or not step_ids:
        return False
    for s in steps:
        if not isinstance(s, dict):
            return False
        if s.get("laneId") not in lane_ids:
            return False
    return True
