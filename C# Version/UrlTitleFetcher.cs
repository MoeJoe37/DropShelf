using System;
using System.Net.Http;
using System.Text.RegularExpressions;
using System.Threading.Tasks;

namespace DropShelf
{
    public static class UrlTitleFetcher
    {
        private static readonly HttpClient _http = new HttpClient();

        static UrlTitleFetcher()
        {
            _http.Timeout = TimeSpan.FromSeconds(4);
            _http.DefaultRequestHeaders.UserAgent.ParseAdd("Mozilla/5.0");
        }

        public static async Task<string?> FetchTitleAsync(string url)
        {
            try
            {
                var response = await _http.GetAsync(url);
                string html = await response.Content.ReadAsStringAsync();
                var match = Regex.Match(html, @"<title[^>]*>(.*?)</title>",
                    RegexOptions.IgnoreCase | RegexOptions.Singleline);
                if (match.Success)
                    return System.Web.HttpUtility.HtmlDecode(match.Groups[1].Value.Trim());
            }
            catch { }
            return null;
        }
    }
}
