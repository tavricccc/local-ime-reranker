import math
from dataclasses import asdict, dataclass, replace


@dataclass(frozen=True)
class Policy:
    semantic_weight: float = 0.9
    rank_penalty: float = 0.18
    quality_weight: float = 0.15
    min_probability: float = 0.75
    min_margin: float = 0.20
    max_promotion: int = 7


def rerank(candidates: list[dict], probabilities: list[float], policy: Policy,
           abstention_probability: float = 0.0) -> dict:
    original = list(range(len(candidates)))
    if len(probabilities) != len(candidates) or not probabilities:
        raise ValueError("model scores must match the candidate snapshot")
    if any(not math.isfinite(p) or p < 0 or p > 1 for p in [*probabilities, abstention_probability]):
        raise ValueError("invalid probability")
    if not math.isclose(sum(probabilities) + abstention_probability, 1.0, abs_tol=0.02):
        raise ValueError("probabilities must sum to one")
    ranked = sorted(original, key=lambda i: (-probabilities[i], i))
    winner = ranked[0]
    margin = probabilities[winner] - (probabilities[ranked[1]] if len(ranked) > 1 else 0)
    result = {"order": original, "reason": "low_confidence", "probabilities": probabilities,
              "margin": margin, "policy": asdict(policy)}
    if abstention_probability >= probabilities[winner]:
        result["reason"] = "model_abstained"
        return result
    if (probabilities[winner] < policy.min_probability or margin < policy.min_margin
            or winner > policy.max_promotion):
        return result
    q0 = candidates[0]["quality"]
    # Candidate quality is Rime's own score, already affected by user dictionary.
    # Rank stays an independent prior because scores from different translators differ.
    fused = [(-policy.rank_penalty * i
              + policy.quality_weight * max(-6, min(6, c["quality"] - q0))
              + policy.semantic_weight * math.log(max(probabilities[i], 1e-8)))
             for i, c in enumerate(candidates)]
    promoted = max(original, key=lambda i: (fused[i], -i))
    order = [promoted] + [i for i in original if i != promoted]
    result.update(order=order, scores=fused,
                  reason="accepted")
    return result


def apply_scores(candidates, probabilities, metadata, policy):
    count = metadata.get("scored_count", len(candidates))
    if not 1 <= count <= len(candidates):
        raise ValueError("scored_count must refer to the original candidate prefix")
    scopes = {(c.get("start"), c.get("end")) for c in candidates[:count]}
    if len(scopes) > 1:
        # Sentence and prefix quality scores are on different native scales.
        # Retain confidence gates and a small original-rank preference.
        policy = replace(policy, quality_weight=0, rank_penalty=min(policy.rank_penalty, .03),
                         max_promotion=count - 1)
    result = rerank(candidates[:count], probabilities, policy,
                    metadata.get("abstention_probability", 0))
    # Candidates outside the model's shortlist retain their original positions.
    result["order"] += list(range(count, len(candidates)))
    return result
