BACKENDS = ["laya", "mlm", "julia", "verdict", "nanojev", "qwen", "jev"]


def create_scorer(args):
    if args.backend == "jev":
        from .jev_model import JevScorer
        return JevScorer(args.model, args.reverse, args.input_mode, args.prompt, args.top_k)
    if args.backend == "laya":
        from .model import LayaScorer
        return LayaScorer(args.model, args.threads, args.reverse)
    if args.backend == "mlm":
        from .masked_model import MaskedScorer
        return MaskedScorer(args.model, args.threads, args.mlm_mode)
    if args.backend == "julia":
        from .julia_model import JuliaScorer
        return JuliaScorer(args.model, args.threads, args.reverse, args.input_mode,
                           args.prompt, args.top_k, args.text_mode)
    if args.backend == "verdict":
        from .verdict_model import VerdictScorer
        return VerdictScorer(args.model, args.threads)
    if args.backend == "nanojev":
        from .nanojev_model import NanoJevScorer
        return NanoJevScorer(args.model, args.threads)
    if args.backend == "qwen":
        from .causal_model import CausalScorer
        return CausalScorer(args.model, args.threads, args.input_mode)
    raise ValueError(args.backend)
