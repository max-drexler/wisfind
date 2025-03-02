"""wisfind.parser

Parse command-line arguments.
"""


USAGE = "usage: wisfind [-V] [-I] [-D [KEY ...]] [TOPIC | URI] [CONSTRAINT ...] [ACTION]"

HELP = """{usage}



""".format(usage=USAGE)


class ParserError(ValueError):
    """Error parsing the command-line arguments"""


def action_emit_json(end="\n", indent: int | None=None) -> ActionFuncType:
    """Initialize an action that prints messages to stdout as JSON string.

    Args:
        end (str): String to print after each message's JSON. Default is '\n'.
        indent (int | None): How many spaces to indent each key in the JSON output.
        Default is None.

    Returns:
        ActionFuncType: A function that prints each message to stdout as a JSON string.
    """

    def emit(msg: WNM | dict) -> None:
        """Prints the WNM to stdout as a JSON string."""
        data = msg.model_dump_json(indent=indent) if isinstance(msg, WNM) else json.dumps(msg, indent=indent)
        print(data, end=end)

    return emit


def constraint_match(match_expr: str) -> Callable[[WNM | dict], bool]:
    key, eq, val = match_expr.partition('=')
    if not eq:
        raise ValueError("match expression must be in format: key=value.")

    def match(msg: WNM | dict) -> bool:
        if msg[key] == val:
            return True
        return False
    return match


def action_format_json(fmt_str: str) -> ActionFuncType:
    pass


class OptType(Enum):
    action = ''
    constraint = ''


class OptDef(TypedDict):
    opt_type: OptType
    default: None
    nargs: int | Literal['?']


PARSER_OPTS = {
    # Actions
    '-print': {
        'definition': {
            'opt_type': OptType.action,
            'nargs': 0,
        },
        'callback': action_emit_json(),
    },
    '-pprint': {
        'definition': {
            'opt_type': OptType.action,
            'nargs': 0,
        },
        'callback': action_emit_json(indent=2),
    },
    '-print0': {
        'definition': {
            'opt_type': OptType.action,
            'nargs': 0,
        },
        'callback': action_emit_json(end='\0')
    },

    # Constraints
    '-match': {
        'definition': {
            'opt_type': OptType.constraint,
            'nargs': 1,
        },
        'callback': constraint_match,
    },
}


DEFAULT_ACTION = PARSER_OPTS['-pprint']


def compose_constraints_and_action(constraint_list, action) -> Callable[[WNM | dict], None]:
    pass


def consume_nargs(nargs, args):
    pass


def parse_args(args) -> Callable[[WNM | dict], None]:
    constraints = []
    action = None
    i = 0
    while i < len(args):
        arg = args[i]

        if arg not in PARSER_OPTS:
            raise ParserError("Got unknown argument: '{}'".format(arg))

        option = PARSER_OPTS[arg]
        if option['definition']['opt_type'] is OptType.action:
            if action is not None:
                raise ParserError("Cannot specify multiple actions!")
            else:
                
                TODO
        else:
            TODO


    if action is None:
        action = DEFAULT_ACTION

    return compose_constraints_and_action(constraints, action)


