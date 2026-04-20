# sfacg_downloader（下载功能优化）

Here's a small tool to download light novels from SF. It has the ability to download paid chapters, but please note, a subscription is required to enable this feature.The novel ID is the string of numbers contained in the box.
![image](https://github.com/NeiHanH/sfacg_downloader/blob/main/p1.png)
~~.SFCommunity and session_APP need to be captured by yourself using a packet capture tool.~~

Now, you can log in using your mobile number and password.
修改说明（仅修改sfacg_downloader.py文件）：
1.当章节下载失败时，进行重试（重试的次数相关配置保存在cookie.txt中，默认最多重试三次）

2.当完成整体的下载之后，在打包之前，提出选项框，在选项框内可以对之前下载错误的章节进行重试，并且放回到相对应的目录中

3.多线程下载，同时下载3~5章，且同样下载后排列为正确的顺序（同样配置保存在cookie.txt中，可修改）
