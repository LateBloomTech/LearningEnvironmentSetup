# pythonコード学習記録


**9/23**要件定義書2.2.1、2.4．に基づいてまずpythonにおけるCPUベンチコード探すも、シングルコアのみのベンチマークページ発見する。

CPUbench.py作成、入力し動作確認する。

**9/24**WINDOWSOSにてpythonコードでマルチコアのベンチマークのコードを掲載しているページ見つからず、LinuXのページ発見し、CPUbench2.py作成、入力途中とする。

**9/25**
VSCにて入力しようとするとpylanceなる拡張機能がbasicにとりあえず設定しました。
strictモードを体験する為、今まで問題なく動いてたCPUbench.pyにて# pyright:strictを先頭に置くとエラーが３つ出現。とりあえず引き続きbasicで様子見ます。
詳細https://qiita.com/simonritchie/items/33ca57cdb5cb2a12ae16

WSLを用いてLinuXの仮想化を行い検証を行うか、出来るならコードを改変し、WINDOWS環境で実行できないか今後検討する。