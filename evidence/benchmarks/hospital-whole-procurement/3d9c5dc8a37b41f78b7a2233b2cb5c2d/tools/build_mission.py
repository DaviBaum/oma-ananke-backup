"""Bind researched stock assumptions to actual measured Hospital profile groups."""
from pathlib import Path
import argparse, hashlib, importlib.util, json

STAGE = Path(__file__).resolve().parent

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('takeoff_directory', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--retain-oversize', action='store_true')
    args = parser.parse_args()
    path = STAGE / 'cost-research/20261022/policy_builder.py'
    spec = importlib.util.spec_from_file_location('campaign_prices', path)
    prices = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prices)
    policies, metadata, labels, inputs = {}, {}, {}, {}
    for path in sorted(args.takeoff_directory.glob('*.takeoff.json')):
        takeoff = json.loads(path.read_text(encoding='utf-8'))
        inputs[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        labels[takeoff['source_sha256']] = takeoff['source_discipline']
        for piece in takeoff['pieces']:
            policy = prices.policy_for(piece)
            if policy is None:
                continue
            if args.retain_oversize:
                policy['long_segments'] = 'RETAIN_OVERSIZE'
            gid = piece['stock_group']
            if gid in policies and policies[gid] != policy:
                raise ValueError('Group has nonuniform policy: ' + gid)
            policies[gid], metadata[gid] = policy, prices.price_metadata(piece)
    assert len(labels) == 7
    mission = dict(schema='oma.whole-building-procurement/1', source_disciplines=labels,
        stock_policies={}, group_policies=policies, currency='USD', search_node_budget=2_000_000)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(mission, indent=2)+'\n', encoding='utf-8')
    args.output.with_suffix('.basis.json').write_text(json.dumps(dict(takeoffs=inputs,
        price_metadata=metadata, references=prices.REFS, policy_builder_sha256=hashlib.sha256((STAGE / 'cost-research/20261022/policy_builder.py').read_bytes()).hexdigest()), indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(mission=str(args.output), groups=len(policies), sources=len(labels))))

if __name__ == '__main__':
    main()
