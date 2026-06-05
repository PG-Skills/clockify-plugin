from datetime import date, timedelta


def business_days(start: date, end: date) -> list[date]:
    """Lista as datas seg–sex no intervalo [start, end] (inclusive).

    Não filtra feriados — isso é podado manualmente na conversa do /lancar-dias.
    Levanta ValueError se start > end.
    """
    if start > end:
        raise ValueError(f"start ({start}) não pode ser depois de end ({end})")
    dias: list[date] = []
    atual = start
    while atual <= end:
        if atual.weekday() < 5:  # 0=seg ... 4=sex; 5=sáb, 6=dom
            dias.append(atual)
        atual += timedelta(days=1)
    return dias
