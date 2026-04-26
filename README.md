# sfacg_downloader（下载功能优化）
## https://github.com/CarrotsPie/sfacg_downloader 原链接，请给原作者点个star
##原作者已更新多线程等功能，可直接前往原项目，但本项目dictionaryMake依旧可用

## 使用方法：
1.直接运行sfacg_downloader.py文件，会读取dict.json
2.如有文字乱码的问题，请先删除原有的dict.json，再运行dictionaryMake_optimized.py
(说明：dictionaryMake_optimized.py会读取novelList.txt中小说的免费章节，进行dict.json的创建，如果懒得找novelList,也可以用我的）

## 修改说明：
### sfacg_downloader.py文件：
1.当章节下载失败时，进行重试（重试的次数相关配置保存在cookie.txt中，默认最多重试三次）
2.当完成整体的下载之后，在打包之前，提出选项框，在选项框内可以对之前下载错误的章节进行重试，并且放回到相对应的目录中
3.多线程下载，同时下载3~5章，且同样下载后排列为正确的顺序（同样配置保存在cookie.txt中，可修改）

### dictionaryMake_optimized.py
1.实现多线程和自动重试（和sfacg_downloader.py配置一致，读取cookie.txt设置）
2.使用cookie.txt中的账号登录，以保证安卓API不会返回内容为0，浏览器模拟仍使用游客

###注意：各项设置0请自行设置，如有问题概不负责。

## 原简介：
Here's a small tool to download light novels from SF. It has the ability to download paid chapters, but please note, a subscription is required to enable this feature.The novel ID is the string of numbers contained in the box.
![image](https://github.com/NeiHanH/sfacg_downloader/blob/main/p1.png)
~~.SFCommunity and session_APP need to be captured by yourself using a packet capture tool.~~

Now, you can log in using your mobile number and password.

