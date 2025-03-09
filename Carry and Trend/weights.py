# Import the required packages
from AlgorithmImports import *

def GetWeights(group):
    subclasses = {}
    for class_, subclass in group.values():
        if class_ not in subclasses:
            subclasses[class_] = {subclass: 0}
        elif subclass not in subclasses[class_]:
            subclasses[class_][subclass] = 0
        subclasses[class_][subclass] += 1

    class_total = len(subclasses.keys())
    subclass_total = {class_: len(subclass.keys()) for class_, subclass in subclasses.items()}
    
    weights = {}
    for ticker in group:
        class_, subclass = group[ticker]
        weight = 1 / class_total / subclass_total[class_] / subclasses[class_][subclass]
        weights[ticker] = weight
    
    return weights