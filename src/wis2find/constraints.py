"""wiswatch.tests"""

from typing import Callable

from wiswatch.definitions import WNM

ConstraintType = Callable[[WNM], bool]
ActionType = Callable[[WNM, ...], None]

## Somehow represent the "constraint"
##
## class WNMConstraint
## -pubtime

## if all(f(WNM[key] for f in pipeline):
##  action(WNM)



def construct_filter() -> ConstraintType:
    pass


## Constraint constructors
##
## Constructors are passed information about the constraint. They must
## parse the information and either raise an error or return a valid ConstraintType.


def t_pubtime(expr: str) -> ConstraintType:
    pass


def t_start_dt(expr: str) -> ConstraintType:
    pass


def t_end_dt(expr: str) -> ConstraintType:
    pass


## Operators


def o_not(f: ConstraintType) -> ConstraintType:
    return functools.partial(filterfalse, f)


def o_or(f1: ConstraintType, f2: ConstraintType) -> ConstraintType:
    # -pubtime 123 -o -pubtime 324
    pass


def o_and(f1: ConstraintType, f2: ConstraintType) -> ConstraintType:
    pass


# -pubtime -10 -start-dt -100
# for msg in filter(t_start_dt(expr), filter(t_pubtime(expr), msg_iter)):
#   msg.action
#
# -pubtime -10 -o -start-dt -100
# for msg in filter(t_or(t_pubtime(expr), t_start_dt(expr)), msg_iter)
#   msg.action
