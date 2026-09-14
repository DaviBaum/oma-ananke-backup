from pathlib import Path
p=Path(__file__).resolve().parent
text=(p/'prepare_and_check.py').read_text(encoding='utf8')
start=text.index("    tests=['tests/test_coupled_tree_integration.py'")
end=text.index('    prefix=',start)
text=text[:start]+"    tests=['tests/test_coupled_tree_integration.py']\n"+text[end:]
text=text.replace("assert len(nodes)==len(set(nodes)) and len(nodes)>617,len(nodes)","assert len(nodes)==len(set(nodes))==20,len(nodes)")
out=p/'check_corrected_integration.py';assert not out.exists()
out.write_text(text,encoding='utf8');compile(text,str(out),'exec')
print(out)
